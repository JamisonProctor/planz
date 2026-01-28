from app.scripts.extract_muenchen_kinder import build_parser


def test_extract_muenchen_parser_accepts_no_sync_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["--no-sync"])
    assert args.no_sync is True


def test_extract_muenchen_parser_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert args.no_sync is False
