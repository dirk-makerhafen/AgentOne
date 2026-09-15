from wiki_find_unlinked_raw import _extract_date_from_path


def test_extract_date_from_path():
    assert _extract_date_from_path("raw/emails/x/received/2020/08/file.md") == "2020-08"
    assert _extract_date_from_path("raw/scans/2021/03/15/scan.pdf") == "2021-03-15"
    assert _extract_date_from_path("raw/emails/x/received/2020/01/02/msg/message.md") == "2020-01-02"
    assert _extract_date_from_path("raw/unknown/2020/04/file.md") == "2020-04"
    assert _extract_date_from_path("concepts/normal.md") == ""
