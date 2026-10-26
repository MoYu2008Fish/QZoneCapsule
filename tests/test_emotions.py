from qzone_archiver.emotions import EMOTIONS, emotion_description, plain_qq_text, qq_html


def test_classic_faces_use_emoji_and_keep_normal_unicode():
    assert plain_qq_text("你好[em]e100[/em] [em]e179[/em]😊") == "你好🙂 👍😊"
    assert "Emoji替代" in qq_html("[em]e100[/em]")
    assert plain_qq_text("[em]e400833[/em]") == "😋"
    assert all(str(code) in EMOTIONS for code in range(100, 205))
    assert plain_qq_text("[em]e190[/em][em]e199[/em][em]e213[/em]") == "💑👋🎉"


def test_verified_new_ids_are_explicit_not_inferred_from_other_namespaces():
    assert plain_qq_text("[em]e400067[/em][em]e400118[/em][em]e401335[/em]") == "🈵🌻🌧️"
    assert plain_qq_text("[em]e10277[/em][em]e257907[/em]") == "🐶⬇️"
    assert "e401335" in qq_html("[em]e401335[/em]")


def test_unknown_faces_use_neutral_emoji_with_unconfirmed_identity_in_description():
    text = "[em]e999999[/em]"
    assert plain_qq_text(text) == "😶"
    assert "未确认" in qq_html(text) and "e999999" in qq_html(text)
    assert "[QQ表情" not in qq_html(text)
    assert "未确认" in emotion_description(text)
    assert "e999999" in emotion_description(text)
    assert plain_qq_text("[EM] e999999 [/EM]") == "😶"


def test_rendered_text_escapes_html_and_preserves_linebreaks():
    html = qq_html("<script>x</script>\n[em]e100[/em]")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<br>" in html and "🙂" in html
