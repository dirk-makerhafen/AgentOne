from __future__ import annotations

import os
import urllib.parse
from typing import Any


def webSearch(query: str, num_results: int = 8) -> tuple[bool, dict]:
    '''
    Search the web for real-time information.

    - Performs a web search and returns up-to-date information.
    - Returns search results with titles, URLs, and snippets.
    - Use this for current events, recent information, or topics
      beyond training data.

    Args:
        query: The search query.
        num_results: Number of search results to return. Default: 8.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - results: list of dicts with 'title', 'url', 'snippet'
            - query: str
        On error, result contains:
            - status: "error"
            - message: str
    '''
    try:
        if not query:
            return (False, {'status': 'error', 'message': 'Search query not provided'})

        api_key = os.environ.get('AGENTONE_SEARCH_API_KEY', '')
        search_engine_id = os.environ.get('AGENTONE_SEARCH_ENGINE_ID', '')

        if api_key and search_engine_id:
            from googleapiclient.discovery import build
            service = build("customsearch", "v1", developerKey=api_key)
            res = service.cse().list(q=query, cx=search_engine_id, num=min(num_results, 10)).execute()
            items = []
            for item in res.get('items', []):
                items.append({
                    'title': item.get('title', ''),
                    'url': item.get('link', ''),
                    'snippet': item.get('snippet', ''),
                })
            return (True, {
                'status': 'success',
                'results': items,
                'query': query,
            })
        else:
            import httpx
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            headers = {'User-Agent': 'AgentOne/1.0'}
            response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
            response.raise_for_status()

            from html.parser import HTMLParser

            class DuckParser(HTMLParser):
                '''Parse DuckDuckGo HTML search results.'''

                def __init__(self) -> None:
                    super().__init__()
                    self.results: list[dict[str, str]] = []
                    self.current: dict[str, Any] = {}
                    self.in_result: bool = False
                    self.in_snippet: bool = False

                def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                    '''Process opening tags to identify result links and snippets.

                    Args:
                        tag: HTML tag name.
                        attrs: List of (name, value) attribute pairs.
                    '''
                    attrs_dict = {k: v for k, v in attrs}
                    cls = attrs_dict.get('class', '')
                    if tag == 'a' and cls and 'result__a' in cls:
                        self.in_result = True
                        self.current = {'url': attrs_dict.get('href', '')}
                    if tag == 'a' and cls and 'result__snippet' in cls:
                        self.in_snippet = True

                def handle_data(self, data: str) -> None:
                    '''Collect title and snippet text.

                    Args:
                        data: Text content inside the current tag.
                    '''
                    if self.in_result and data.strip():
                        self.current.setdefault('title', '')
                        if self.current['title'] is not None:
                            self.current['title'] += data.strip()
                    if self.in_snippet and data.strip():
                        self.current.setdefault('snippet', '')
                        if self.current['snippet'] is not None:
                            self.current['snippet'] += data.strip()

                def handle_endtag(self, tag: str) -> None:
                    '''Process closing tags to finalize a result entry.

                    Args:
                        tag: HTML tag name.
                    '''
                    if tag == 'a' and self.in_snippet:
                        self.in_snippet = False
                    if tag == 'a' and self.in_result and self.current.get('title'):
                        s = self.current.get('url', '')
                        if s and s.startswith('/'):
                            from urllib.parse import parse_qs, urlparse
                            parsed = urlparse(self.current['url'])
                            params = parse_qs(parsed.query)
                            if 'uddg' in params:
                                self.current['url'] = params['uddg'][0]
                        self.results.append(self.current)
                        self.current = {}
                        self.in_result = False

            parser = DuckParser()
            parser.feed(response.text)
            items = parser.results[:num_results]

            return (True, {
                'status': 'success',
                'results': items,
                'query': query,
            })

    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'Error searching for "{query}": {str(e)}\n{traceback.format_exc()}'})

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Search the web.')
    parser.add_argument('query', type=str, help='Search query')
    parser.add_argument('--num-results', type=int, default=8, help='Number of results')
    args = parser.parse_args()

    success, result = webSearch(query=args.query, num_results=args.num_results)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
