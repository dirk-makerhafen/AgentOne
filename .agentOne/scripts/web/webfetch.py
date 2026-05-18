import httpx
import os

def webFetch(caller, url, format="markdown"):
    '''
    Fetches content from a specified URL.

    - Takes a URL and optional format as input.
    - Fetches the URL content, converts to requested format (markdown by default).
    - Use this tool when you need to retrieve and analyze web content.
    - The URL must be a fully-formed valid URL.
    - HTTP URLs will be automatically upgraded to HTTPS.

    Args:
        url (str): The URL to fetch content from.
        format (str): The format to return the content in ("text", "markdown", or "html"). Default: "markdown".

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'content': str
                - 'url': str
            On error, result contains:
                - 'status': 'error'
                - 'message': str
    '''
    try:
        if not url:
            return (False, {'status': 'error', 'message': 'URL not provided'})

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        headers = {
            'User-Agent': 'AgentOne/1.0'
        }

        response = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
        response.raise_for_status()

        if format == "html":
            content = response.text
        elif format == "text":
            import re
            content = re.sub(r'<[^>]+>', '', response.text)
            content = re.sub(r'\n\s*\n', '\n\n', content).strip()
        else:
            content = response.text
            try:
                import markdownify
                content = markdownify.markdownify(content, heading_style="ATX")
            except ImportError:
                import re
                content = re.sub(r'<[^>]+>', '', response.text)
                content = re.sub(r'\n\s*\n', '\n\n', content).strip()

        return (True, {
            'status': 'success',
            'content': content,
            'url': url
        })

    except httpx.RequestError as e:
        return (False, {'status': 'error', 'message': f'Failed to fetch {url}: {str(e)}'})
    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'Error fetching {url}: {str(e)}\n{traceback.format_exc()}'})

if __name__ == '__main__':
    import argparse
    import json

    class MockCaller:
        def __init__(self):
            self.workingdir = os.getcwd()

    parser = argparse.ArgumentParser(description='Fetch content from a URL.')
    parser.add_argument('url', type=str, help='URL to fetch')
    parser.add_argument('--format', type=str, default='markdown', choices=['text', 'markdown', 'html'], help='Output format')
    args = parser.parse_args()

    success, result = webFetch(MockCaller(), url=args.url, format=args.format)
    if success:
        print(result.get('content', ''))
    else:
        print(json.dumps(result, indent=2))
    exit(0 if success else 1)
