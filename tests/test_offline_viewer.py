import json
import re
import shutil
import subprocess

import pytest

from qzone_archiver.exporter import export_bundle
from qzone_archiver.store import Store


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js is optional for offline viewer checks")
def test_mixed_timeline_emoji_and_account_switch_in_offline_script(tmp_path):
    with Store(tmp_path / "qzone.db") as store:
        for uin, content in (("123", "甲账号的回忆"), ("456", "乙账号的回忆")):
            store.upsert_account(uin)
            store.upsert_album(uin, {"id": "a", "name": "同名相册[em]e213[/em]"})
            store.upsert_photo(uin, "a", {"sloc": "p", "name": "同名照片"})
            store.upsert_mood(
                uin, {"tid": "m", "content": content + "[em]e100[/em][em]e400118[/em][em]e999999[/em]"}
            )
        index = export_bundle(store, "123", tmp_path)
    script = re.findall(r"<script>(.*?)</script>", index.read_text(), re.DOTALL)[0]
    data = json.loads(
        (tmp_path / "data.js").read_text().removeprefix("window.__QZONE_DATA__ = ").removesuffix(";")
    )
    harness = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(){this.value='';this.innerHTML='';this.events={};this.dataset={};this.classList={toggle:()=>{},add:()=>{},remove:()=>{}};}
  addEventListener(type,fn){this.events[type]=fn;}
  setAttribute(name,value){}
  before(element){globalThis.accountSelect=element;}
  add(option){}
}
const elements=new Map();
const tabs=['timeline','albums','moods','photos'].map(v=>{let e=new Element();e.dataset.view=v;return e;});
const sections=tabs.map(t=>({id:t.dataset.view,classList:{toggle:()=>{}}}));
const document={querySelector(s){if(s==='.tab.active')return tabs[0];if(!elements.has(s))elements.set(s,new Element());return elements.get(s);},querySelectorAll(s){return s==='.tab'?tabs:s==='section'?sections:[];},createElement(){return new Element();},addEventListener(){}};
function Option(text,value){this.text=text;this.value=value;}
const sandbox={document,window:{__QZONE_DATA__:DATA},Option,setTimeout:fn=>fn(),clearTimeout(){}};
vm.runInNewContext(SCRIPT,sandbox);
const html=elements.get('#timeline').innerHTML;
assert(html.includes('甲账号的回忆')&&html.includes('乙账号的回忆'));
assert(html.includes('6 条内容')&&html.includes('同名照片')&&html.includes('同名相册'));
assert(html.includes('🙂')&&!html.includes('[em]e100[/em]'));
assert(html.includes('🌻')&&html.includes('😶')&&html.includes('语义未确认')&&html.includes('原编号 e999999'));
assert(!html.includes('[QQ表情')&&!html.includes('[em]')&&html.includes('🎉'));
accountSelect.value='456';accountSelect.events.change();
const filtered=elements.get('#timeline').innerHTML;
assert(filtered.includes('乙账号的回忆')&&!filtered.includes('甲账号的回忆'));
assert(filtered.includes('3 条内容'));
accountSelect.value='';accountSelect.events.change();
assert(elements.get('#timeline').innerHTML.includes('6 条内容'));
"""
    runner = tmp_path / "check.cjs"
    runner.write_text(
        "const DATA=" + json.dumps(data) + ";const SCRIPT=" + json.dumps(script) + ";\n" + harness
    )
    result = subprocess.run([shutil.which("node"), str(runner)], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
