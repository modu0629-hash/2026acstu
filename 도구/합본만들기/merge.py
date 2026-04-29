"""수복이 합본 생성/갱신 도구

사용법:
    python merge.py                          # 같은 폴더 + 부모 폴더의 *.meta.json 모두 갱신
    python merge.py <합본파일.html>          # 그 합본만 갱신 (옆에 .meta.json 있어야 함)
    python merge.py --init <config.json>     # config.json 보고 새 합본 생성

자세한 사용법: README.md
"""
import re, sys, io, json, base64, datetime, argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TOOL_DIR = Path(__file__).resolve().parent
ENV_CFG  = TOOL_DIR / 'config.json'

# ────────── 설정 로드 (폰트 경로 등) ──────────
def load_env():
    if ENV_CFG.exists():
        return json.loads(ENV_CFG.read_text(encoding='utf-8'))
    return {}

ENV = load_env()
FONT_FULL_DIR = Path(ENV.get('font_full_dir', r'Z:\HDD1\005.함병연 개인폴더\코딩\2026년 학원 스터디\경기서체웹폰트\경기서체웹폰트\woff'))


# ────────── 핵심: HTML 파싱 / 추출 ──────────
SHEET_RE = re.compile(r'(<section class="sheet [^"]+"[^>]*>[\s\S]*?</section>)')

def read(p): return Path(p).read_text(encoding='utf-8')

def extract_top_divs(html, class_token):
    """class_token으로 시작하는 top-level <div>를 nested 처리해서 모두 반환"""
    blocks = []
    i, n = 0, len(html)
    pat = re.compile(rf'<div class="{re.escape(class_token)}\b[^"]*"[^>]*>')
    while True:
        m = pat.search(html, i)
        if not m: break
        start = m.start()
        depth, j = 0, start
        while j < n:
            if html[j] == '<':
                if html[j:j+5].lower() in ('<div ', '<div>'):
                    depth += 1
                    end_tag = html.find('>', j)
                    if end_tag < 0: break
                    j = end_tag + 1
                    continue
                if html[j:j+6].lower() == '</div>':
                    depth -= 1
                    j += 6
                    if depth == 0:
                        blocks.append(html[start:j])
                        i = j
                        break
                    continue
            j += 1
        else:
            break
    return blocks

def renumber(html, offset):
    """pnum/href/data-qa-id/id=sol-/sol-num/qa-num 모두 +offset"""
    if offset == 0: return html
    html = re.sub(
        r'<span class="pnum"><a href="#sol-(\d+)" class="solution-link">\d+</a></span>',
        lambda m: f'<span class="pnum"><a href="#sol-{int(m.group(1))+offset}" class="solution-link">{int(m.group(1))+offset}</a></span>',
        html)
    html = re.sub(r'id="sol-(\d+)"',
        lambda m: f'id="sol-{int(m.group(1))+offset}"', html)
    html = re.sub(r'data-qa-id="q(\d+)"',
        lambda m: f'data-qa-id="q{int(m.group(1))+offset}"', html)
    html = re.sub(
        r'(<(?:div|span) class="sol-num"[^>]*>)(\d+)(\.?</(?:div|span)>)',
        lambda m: f'{m.group(1)}{int(m.group(2))+offset}{m.group(3)}', html)
    html = re.sub(
        r'(<span class="qa-num"[^>]*>)(\d+)(\.?</span>)',
        lambda m: f'{m.group(1)}{int(m.group(2))+offset}{m.group(3)}', html)
    return html


# ────────── 폰트 풀 서브셋 자동 재생성 ──────────
def rebuild_font_subset(text_for_glyphs):
    """합본 본문에 사용된 모든 codepoint로 4종 폰트 서브셋 새로 만듦. base64 dict 반환."""
    from fontTools.subset import Subsetter
    from fontTools.ttLib import TTFont

    # codepoint 수집
    codepoints = set()
    for c in text_for_glyphs:
        cp = ord(c)
        if 0xAC00 <= cp <= 0xD7A3: codepoints.add(cp)        # 한글
        elif 0x4E00 <= cp <= 0x9FFF: codepoints.add(cp)      # 한자
        elif 0x20 <= cp <= 0x7E: codepoints.add(cp)          # ASCII
        elif 0x3130 <= cp <= 0x318F: codepoints.add(cp)      # 한글 자모(호환)
        elif 0x1100 <= cp <= 0x11FF: codepoints.add(cp)      # 한글 자모(기본)
    # 자주 쓰는 기호 강제 포함
    for cp in (0x00B7, 0x2026, 0x203B, 0x2190, 0x2192, 0x2194, 0x2200, 0x2203,
               0x2208, 0x2209, 0x2218, 0x2229, 0x222A, 0x2260, 0x2261, 0x2264,
               0x2265, 0x2282, 0x2283, 0x2286, 0x2287, 0x2295, 0x2297, 0x22C5,
               0x2502, 0x25A1, 0x25CB, 0x25CF, 0x25EF, 0x2605, 0x2606, 0x2640,
               0x2642, 0x2660, 0x2661, 0x2662, 0x2663, 0x2664, 0x2665, 0x2666,
               0x2667, 0x2668, 0x2669, 0x266A, 0x266B, 0x266C, 0x266D, 0x266E,
               0x266F, 0x2756, 0x2776, 0x2777, 0x2778, 0x2779, 0x277A, 0x277B,
               0x277C, 0x277D, 0x277E, 0x277F, 0x2780, 0x2781, 0x2782, 0x2783,
               0x2784, 0x2785, 0x2786, 0x2787, 0x2788, 0x2789, 0x2160, 0x2161,
               0x2162, 0x2163, 0x2164, 0x2165, 0x2166, 0x2167, 0x2168, 0x2169,
               0x2170, 0x2171, 0x2172, 0x2173, 0x2174, 0x2175, 0x2176, 0x2177,
               0x2178, 0x2179, 0x2460, 0x2461, 0x2462, 0x2463, 0x2464, 0x2465,
               0x2466, 0x2467, 0x2468, 0x2469, 0x246A, 0x246B, 0x246C, 0x246D,
               0x246E, 0x246F, 0x2474, 0x2475, 0x2476, 0x2477, 0x2478, 0x2479,
               0x247A, 0x247B, 0x247C, 0x247D, 0x2153, 0x2154, 0x2155, 0x2156,
               0x2157, 0x2158, 0x2159, 0x215A, 0x215B, 0x215C, 0x215D, 0x215E,
               0x00B1, 0x00D7, 0x00F7, 0x00B0, 0x2032, 0x2033, 0x221A, 0x221E,
               0x2220, 0x222B, 0x2211, 0x220F, 0x00A0, 0x3000, 0x300C, 0x300D,
               0x300E, 0x300F, 0x3010, 0x3011, 0xFF08, 0xFF09, 0xFF0C, 0xFF0E,
               0xFF1A, 0xFF1B, 0x2018, 0x2019, 0x201C, 0x201D, 0x2014, 0x2013):
        codepoints.add(cp)

    # 4종 폰트 서브셋 생성
    out = {}
    for stem in ['Title_Bold', 'Title_Medium', 'Batang_Regular', 'Batang_Bold']:
        src = FONT_FULL_DIR / f'{stem}.woff'
        if not src.exists():
            print(f'  ✗ 풀 폰트 없음: {src}')
            continue
        font = TTFont(src)
        sub = Subsetter()
        sub.populate(unicodes=list(codepoints))
        sub.subset(font)
        font.flavor = 'woff'
        # 임시 파일 거치지 않고 메모리에서 base64
        from io import BytesIO
        buf = BytesIO()
        font.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode('ascii')
        out[stem] = b64
    return out


# ────────── 합본 빌드 ──────────
def build_merged(units, base_html_path, title, header_odd, header_even, output_path):
    """units = [(name, file_path)] (offset 자동 계산)
    base_html_path = head/CSS/script 베이스 파일 (보통 마지막 단원 파일)
    """
    # 1) units 데이터 추출
    all_main_sheets, all_qa_items, all_sol_items = [], [], []
    cum = 0
    summary = []
    for name, fp in units:
        html = read(fp)
        body = re.search(r'<body[^>]*>([\s\S]*)</body>', html).group(1)
        body = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', body)
        sheets = SHEET_RE.findall(body)
        m_count = q_count = s_count = 0
        for sh in sheets:
            cls = re.search(r'<section class="sheet ([^"]+)"', sh).group(1)
            sh_r = renumber(sh, cum)
            if 'quick-answer-section' in cls:
                items = re.findall(r'<div class="qa-item"[^>]*>[\s\S]*?</div>', sh_r)
                all_qa_items.extend(items)
                q_count = len(items)
            elif 'solution-section' in cls:
                items = extract_top_divs(sh_r, 'solution-item')
                all_sol_items.extend(items)
                s_count = len(items)
            else:
                all_main_sheets.append(sh_r)
                m_count += 1
        summary.append((name, m_count, q_count, s_count, cum))
        cum += q_count

    print(f'\n=== 단원별 추출 (총 {cum}문항) ===')
    for n, m, q, s, off in summary:
        print(f'  {n:25s} main={m:2d} qa={q:2d} sol={s:2d} offset={off}')
    assert len(all_qa_items) == cum, f'qa-item {len(all_qa_items)} != {cum}'
    assert len(all_sol_items) == cum, f'sol-item {len(all_sol_items)} != {cum}'

    total = cum

    # 2) 베이스: 자급 임베드 단원 파일에서 head/script
    base = read(base_html_path)
    m = re.search(r'^([\s\S]*?<body[^>]*>)([\s\S]*)(</body>\s*</html>\s*)$', base)
    head_block, base_body, end_block = m.group(1), m.group(2), m.group(3)
    head_block = re.sub(r'<title>[^<]*</title>', f'<title>{title}</title>', head_block)
    scripts = re.findall(r'<script[^>]*>[\s\S]*?</script>', base_body)
    scripts_html = '\n'.join(scripts)

    # 3) 통합 sheet 생성
    qa_sheet = (
        '<section class="sheet odd quick-answer-section">\n'
        '  <div class="corner tr"></div><div class="corner tl"></div>'
        '<div class="corner br"></div><div class="corner bl"></div>\n'
        f'  <header class="sheet-header">{header_odd}</header>\n'
        '  <div class="sheet-body">\n'
        '    <h2 class="section-title">빠른 정답</h2>\n'
        '    <div class="quick-answers">\n'
        + '\n'.join('      ' + it for it in all_qa_items) + '\n'
        '    </div>\n'
        '  </div>\n'
        '  <footer class="sheet-footer"></footer>\n'
        '</section>\n'
    )
    sol_sheet = (
        '<section class="sheet odd solution-section">\n'
        '  <div class="corner tr"></div><div class="corner tl"></div>'
        '<div class="corner br"></div><div class="corner bl"></div>\n'
        f'  <header class="sheet-header">{header_odd}</header>\n'
        '  <div class="sheet-body">\n'
        '    <h2 class="section-title">정답 및 해설</h2>\n'
        '    <div class="solutions">\n\n'
        + '\n\n'.join('      ' + it for it in all_sol_items) + '\n\n'
        '    </div>\n'
        '  </div>\n'
        '  <footer class="sheet-footer"></footer>\n'
        '</section>\n'
    )

    # 4) 합본 보강 JS (빠른정답 flex 분배 + squash)
    extra_js = build_extra_js(header_odd, header_even)

    combined = '\n' + '\n'.join(all_main_sheets) + '\n\n' + qa_sheet + '\n' + sol_sheet + '\n' + scripts_html + '\n' + extra_js + '\n'
    final = head_block + combined + end_block

    # 5) 후처리
    # 5a) 폰트 풀 서브셋 재생성
    text_for_glyphs = re.sub(r'<[^>]+>', ' ', re.sub(r'<script[\s\S]*?</script>', '', final))
    text_for_glyphs = re.sub(r'<style[\s\S]*?</style>', '', text_for_glyphs)
    fonts_b64 = rebuild_font_subset(text_for_glyphs)
    final = replace_fonts(final, fonts_b64)

    # 5b) 빠른정답 flex 3-col 강제 + 해설 자연 break + 마커 제거
    final = patch_qa_flex_sol_native(final)

    # 6) 저장
    Path(output_path).write_text(final, encoding='utf-8')
    sz = Path(output_path).stat().st_size
    print(f'\n✓ {Path(output_path).name} 생성 ({sz:,} bytes)')

    # 7) 정합성 검증
    assert_valid(final, total)

    return total


def replace_fonts(html, fonts_b64):
    """@font-face의 base64 4종 교체 (family + weight 매칭)"""
    n_total = 0
    for stem, family, weight in [
        ('Title_Bold',     'Gyeonggi Title',  700),
        ('Title_Medium',   'Gyeonggi Title',  500),
        ('Batang_Regular', 'Gyeonggi Batang', 400),
        ('Batang_Bold',    'Gyeonggi Batang', 700),
    ]:
        if stem not in fonts_b64: continue
        b64 = fonts_b64[stem]
        pat = re.compile(
            rf"(@font-face\s*\{{\s*font-family:'{re.escape(family)}';\s*src:url\('data:font/woff;base64,)"
            rf"[^']+"
            rf"(\'\)\s+format\('woff'\);\s*font-weight:{weight};[^}}]*\}})",
            re.IGNORECASE
        )
        html, n = pat.subn(lambda m: m.group(1) + b64 + m.group(2), html)
        n_total += n
    print(f'  @font-face 교체: {n_total}건')
    return html


def patch_qa_flex_sol_native(html):
    """빠른정답 flex 3-col / 해설 자연 column break.

    v1.2 변경 (`/mathbook:과목별교재:_공통` v1.3 동기): (이어서) 마커는 그대로 유지.
    행렬 인쇄본 스타일이 자연 흐름에 더 자연스럽다는 사용자 피드백 반영.
    """
    # 빠른정답: flex 3-col
    new_qa = (
        '.quick-answers { flex:1 1 auto; min-height:0; position:relative; display:flex; gap:7mm; '
        "font-family:'신명조','HY신명조','Shinmyeongjo','바탕','Batang',serif; "
        'font-size:8pt; line-height:1.85; letter-spacing:-0.1em; }'
    )
    html = re.sub(r'\.quick-answers\s*\{[^}]*\}', new_qa, html, count=1)
    if '.quick-answers > .col {' not in html:
        html = html.replace('.quick-answers::before',
            '.quick-answers > .col { flex:1 1 0; min-width:0; overflow:hidden; }\n    .quick-answers::before', 1)
    extra_qa_css = (
        '.qa-item { overflow-wrap:anywhere; word-break:break-word; max-width:100%; }\n'
        '    .qa-ans  { overflow-wrap:anywhere; word-break:break-word; }\n'
        '    .qa-ans mjx-container { max-width:100%; overflow:visible; white-space:normal; }\n'
        '    .qa-ans mjx-container[display="false"] { display:inline-block; max-width:100%; }\n'
    )
    if '/* qa-wrap-extra */' not in html:
        html = html.replace('.quick-answers > .col {',
            '/* qa-wrap-extra */\n    ' + extra_qa_css + '    .quick-answers > .col {', 1)

    # qa-item / solution-item에서 break-* 제거
    for sel in ['qa-item', 'solution-item']:
        html = re.sub(
            rf'(\.{sel}\s*\{{)([^}}]*)(\}})',
            lambda m: m.group(1) + re.sub(
                r'(?:-webkit-column-break-inside|page-break-inside|break-inside)\s*:\s*[^;]+;?\s*',
                '', m.group(2)).strip() + m.group(3),
            html, count=1
        )

    # (이어서) 마커는 v1.2부터 활성 유지 — 별도 patch 없음
    # (만약 단원 파일에서 마커를 비웠다면 여기서 복원)
    html = re.sub(
        r"(\.solution-item\.continuation::before\s*\{\s*content:)\s*''\s*;",
        r"\1 '(이어서) ';", html)

    return html


def build_extra_js(header_odd, header_even):
    """빠른정답 flex 분배 + squash + 헤더/푸터 재부착"""
    return r'''
<script>
document.addEventListener('DOMContentLoaded', () => {
  const wait = () => new Promise(r => {
    if (document.body.classList.contains('ready')) r();
    else { const id = setInterval(() => {
      if (document.body.classList.contains('ready')) { clearInterval(id); r(); }
    }, 50); }
  });
  wait().then(() => {
    function distributeToCols(secs, items, opts) {
      const colCount = opts.colCount, sheetClass = opts.sheetClass, containerSel = opts.containerSel;
      const sectionsRef = secs.slice();
      function ensureCols(sec) {
        const c = sec.querySelector(containerSel);
        if (!c) return null;
        if (c.querySelectorAll(':scope > .col').length !== colCount) {
          c.innerHTML = '';
          for (let k = 0; k < colCount; k++) {
            const d = document.createElement('div');
            d.className = 'col col-' + (k+1);
            c.appendChild(d);
          }
        }
        return c;
      }
      function makeSection() {
        const prev = sectionsRef[sectionsRef.length - 1];
        const ns = document.createElement('section');
        ns.className = sheetClass;
        let colsHtml = '';
        for (let k = 0; k < colCount; k++) colsHtml += '<div class="col col-' + (k+1) + '"></div>';
        ns.innerHTML =
          '<div class="corner tr"></div><div class="corner tl"></div>' +
          '<div class="corner br"></div><div class="corner bl"></div>' +
          '<header class="sheet-header"></header>' +
          '<div class="sheet-body"><div class="' + containerSel.slice(1) + '">' + colsHtml + '</div></div>' +
          '<footer class="sheet-footer"></footer>';
        prev.parentNode.insertBefore(ns, prev.nextSibling);
        sectionsRef.push(ns);
        return ns;
      }
      function colOverflows(col) { void col.offsetHeight; return col.scrollHeight > col.clientHeight + 1; }
      sectionsRef.forEach(sec => ensureCols(sec));
      sectionsRef.forEach(sec => {
        sec.querySelectorAll(':scope ' + containerSel + ' > .col').forEach(c => c.innerHTML = '');
      });
      let queue = items.slice(), secIdx = 0, safety = 0;
      while (queue.length > 0 && safety++ < 3000) {
        if (secIdx >= sectionsRef.length) makeSection();
        const sec = sectionsRef[secIdx];
        const cols = Array.from(sec.querySelectorAll(':scope ' + containerSel + ' > .col'));
        for (const col of cols) {
          while (queue.length > 0) {
            const item = queue[0];
            col.appendChild(item);
            if (colOverflows(col)) { col.removeChild(item); break; }
            queue.shift();
          }
          if (col.children.length === 0 && queue.length > 0) col.appendChild(queue.shift());
          if (queue.length === 0) break;
        }
        secIdx++;
      }
      sectionsRef.forEach(sec => {
        const cs = sec.querySelectorAll(':scope ' + containerSel + ' > .col');
        if (![...cs].some(c => c.children.length > 0)) sec.remove();
      });
    }

    // 빠른정답: 3-col flex 분배
    (function flowQuickAnswers(){
      const secs = Array.from(document.querySelectorAll('.quick-answer-section'));
      if (!secs.length) return;
      const items = [];
      secs.forEach(sec => sec.querySelectorAll('.qa-item').forEach(it => items.push(it)));
      const titleHtml = secs[0].querySelector('.section-title')?.outerHTML || '';
      secs[0].querySelector('.sheet-body').innerHTML = titleHtml + '<div class="quick-answers"></div>';
      for (let i = 1; i < secs.length; i++) {
        secs[i].querySelector('.sheet-body').innerHTML = '<div class="quick-answers"></div>';
      }
      distributeToCols(secs, items, {
        colCount: 3, sheetClass: 'sheet quick-answer-section', containerSel: '.quick-answers'
      });
    })();

    // 해설(.solutions)은 baseline flowSolutions가 처리 (CSS column-fill:auto + 자연 break + 단락 split)
    // v1.2 (`/mathbook:과목별교재:수복이-합본` v1.2 / `/mathbook:과목별교재:_공통` v1.3) — 행렬 스타일 기본화:
    //  - (이어서) 마커 활성 유지 (별도 patch 없음)
    //  - squashShortContinuations / squashTrailingPage 기본 비활성화
    //    필요 시 메타옵션 enable_squash_short: true 로만 옵트인.

    // 헤더·페이지 번호 재부착
    const sheets = document.querySelectorAll('.sheet');
    sheets.forEach((s, i) => {
      const isOdd = (i % 2 === 0);
      s.classList.toggle('odd', isOdd);
      s.classList.toggle('even', !isOdd);
      const hdr = s.querySelector('.sheet-header');
      if (hdr) hdr.textContent = isOdd ? '__HEADER_ODD__' : '__HEADER_EVEN__';
    });
    document.querySelectorAll('.sheet-footer').forEach((f, i) => { f.textContent = i + 1; });
  });
});
</script>
'''.replace('__HEADER_ODD__', header_odd).replace('__HEADER_EVEN__', header_even)


def assert_valid(html, total):
    n_pnum = len(re.findall(r'<span class="pnum">', html))
    n_sol  = len(re.findall(r'id="sol-\d+"', html))
    n_qa   = len(re.findall(r'<div class="qa-item"', html))
    print(f'  검증: pnum={n_pnum}, sol={n_sol}, qa={n_qa} (각 {total} 기대)')
    assert n_pnum == total and n_sol == total and n_qa == total
    ids = sorted(int(m.group(1)) for m in re.finditer(r'id="sol-(\d+)"', html))
    assert ids == list(range(1, total+1)), 'sol-id 1~N 누락/중복'
    print(f'  ✓ sol-id 1~{total} 정확')


# ────────── 메타 파일 처리 ──────────
def update_from_meta(meta_path):
    """meta.json 읽고 합본 갱신"""
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    out_html = meta_path.with_suffix('').with_suffix('.html')
    if not out_html.exists():
        # 메타 파일명에서 .meta.json 떼기
        stem = meta_path.name
        if stem.endswith('.meta.json'):
            out_html = meta_path.parent / stem[:-len('.meta.json')] + '.html'

    units = []
    base_dir = Path(meta.get('base_dir', meta_path.parent))
    if not base_dir.is_absolute():
        base_dir = (meta_path.parent / base_dir).resolve()
    for u in meta['units']:
        units.append((u['name'], base_dir / u['file']))

    base_template = base_dir / meta.get('base_template_file', meta['units'][-1]['file'])

    print(f'━━━ 갱신: {out_html.name} ━━━')
    total = build_merged(
        units=units,
        base_html_path=base_template,
        title=meta['title'],
        header_odd=meta.get('header_odd', '공통수학 1'),
        header_even=meta.get('header_even', '2026 수복이'),
        output_path=out_html,
    )

    # 메타 last_built 갱신
    meta['last_built'] = datetime.datetime.now().isoformat(timespec='seconds')
    meta['total_problems'] = total
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')


def init_from_config(config_path):
    """config.json (단원 목록 명시)으로 새 합본 생성 + meta.json 작성"""
    cfg = json.loads(Path(config_path).read_text(encoding='utf-8'))
    out_dir = Path(cfg.get('out_dir', '.')).resolve()
    out_html = out_dir / f'{cfg["title"]}.html'
    meta_path = out_dir / f'{cfg["title"]}.meta.json'

    base_dir = Path(cfg['base_dir']).resolve()
    units_for_build = [(u['name'], base_dir / u['file']) for u in cfg['units']]
    base_template = base_dir / cfg.get('base_template_file', cfg['units'][-1]['file'])

    print(f'━━━ 새 합본: {out_html.name} ━━━')
    total = build_merged(
        units=units_for_build,
        base_html_path=base_template,
        title=cfg['title'],
        header_odd=cfg.get('header_odd', '공통수학 1'),
        header_even=cfg.get('header_even', '2026 수복이'),
        output_path=out_html,
    )

    # 메타 파일 작성
    meta = {
        'version': '1.0',
        'title': cfg['title'],
        'header_odd': cfg.get('header_odd', '공통수학 1'),
        'header_even': cfg.get('header_even', '2026 수복이'),
        'base_dir': str(base_dir),
        'base_template_file': cfg.get('base_template_file', cfg['units'][-1]['file']),
        'units': cfg['units'],
        'total_problems': total,
        'last_built': datetime.datetime.now().isoformat(timespec='seconds'),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n→ 메타: {meta_path.name}')


# ────────── 메타 파일 자동 검색 ──────────
def find_meta_files(start_dir):
    """start_dir + 부모 디렉토리에서 *.meta.json 검색"""
    found = []
    for d in [start_dir, start_dir.parent, start_dir.parent.parent]:
        if d.exists():
            found.extend(d.glob('*.meta.json'))
            for sub in d.iterdir():
                if sub.is_dir() and not sub.name.startswith('.'):
                    found.extend(sub.glob('*.meta.json'))
    # 중복 제거
    seen = set()
    out = []
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(rp)
    return out


# ────────── main ──────────
def main():
    parser = argparse.ArgumentParser(description='수복이 합본 생성/갱신')
    parser.add_argument('target', nargs='?', help='합본 .html 또는 .meta.json (생략 시 자동 검색)')
    parser.add_argument('--init', metavar='CONFIG', help='새 합본 생성 (config.json 명시)')
    args = parser.parse_args()

    if args.init:
        init_from_config(args.init)
        return

    if args.target:
        p = Path(args.target).resolve()
        if p.suffix == '.json':
            update_from_meta(p)
        elif p.suffix == '.html':
            meta = p.parent / (p.stem + '.meta.json')
            if not meta.exists():
                print(f'✗ 메타 파일 없음: {meta}')
                print('  최초 1회는 --init <config.json>으로 생성하세요.')
                sys.exit(1)
            update_from_meta(meta)
        return

    # 자동 검색
    metas = find_meta_files(TOOL_DIR)
    if not metas:
        print('메타 파일(*.meta.json)을 찾을 수 없어요.')
        print('  최초 합본: python merge.py --init <config.json>')
        return
    print(f'발견된 메타 {len(metas)}개:')
    for m in metas:
        print(f'  - {m}')
    print()
    for m in metas:
        update_from_meta(m)
        print()

if __name__ == '__main__':
    main()
