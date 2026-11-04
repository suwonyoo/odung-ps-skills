"""Local human-operated HR outbox/inbox. No messages, network or auto-application."""
import re

try:
    import harness as h
except ModuleNotFoundError:
    import runner as h


def parse(text):
    """Read exact ## ID sections; never treat fenced examples as question IDs."""
    sections, current, lines, fence = {}, None, [], None
    def finish():
        if current is not None:
            if current in sections:
                raise h.KitError('Duplicate inbox question ID: ' + current)
            sections[current] = ''.join(lines).strip('\r\n')
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
        match = re.fullmatch(r'## ([A-Za-z0-9_-]+)\s*', line) if fence is None and marker is None else None
        if match:
            finish(); current, lines = match.group(1), []
        elif current is not None:
            lines.append(line)
    finish()
    return {key: value for key, value in sections.items() if value.strip()}


def stage_answers(state, text):
    """Validate a whole batch first; retries skip identical already recorded text."""
    staged = []
    for qid, reply in parse(text).items():
        q = state['questions'].get(qid)
        if q is None:
            raise h.KitError('Unknown inbox question ID: ' + qid)
        if any(a['text'] == reply for a in q.get('answers', [])):
            continue
        if q['status'] not in ('pending', 'conflict', 'needs-clarification'):
            raise h.KitError('Changed/already answered inbox ID: ' + qid + '; preserve history and mark conflict or create a follow-up')
        staged.append((qid, reply))
    return staged


def render(root, state):
    inbox = h.safe_path(root, '.harness/work/hr-inbox.md')
    if not inbox.exists():
        with inbox.open('x', encoding='utf-8') as stream:
            stream.write('# 받은 답변 원문\n\n실제로 받은 답변만 아래에 덧붙입니다. 각 답변 위에 `## Q1`처럼 질문 ID를 씁니다.\n기존 원문은 지우거나 고치지 않습니다. 수정 답변은 AI에게 충돌·후속 질문 처리를 요청하세요.\n')
    mode = state.get('contact', {}).get('mode', 'unspecified')
    rows = ['# 전달할 질문', '', '자동 생성 보기. AI가 DM을 보내거나 받지 않습니다. 원문 답변은 hr-inbox.md에 보관합니다.', '']
    if mode != 'manual':
        rows += ['외부 DM 요청 없음. 문서 근거와 필요한 사용자 결정을 확인합니다.', '']
    else:
        for q in state['questions'].values():
            if q['status'] == 'resolved':
                continue
            status = '답변 검토·반영 대기' if q['status'] == 'answered' else '추가 확인 필요' if q['status'] in ('needs-clarification', 'conflict') else '답변 대기' if q.get('delivery') else '전달 대기'
            rows += [f"## {q['id']} · {status}", '', q['text'], '',
                     '- 발견 단계: ' + q['phase'], '- 영향: ' + q['impact'],
                     '- 관련 작업: ' + (', '.join(q['blocks']) or '없음'), '']
            assessment = q.get('assessment', {})
            if assessment.get('followup'):
                rows += ['확인된 범위: ' + assessment['meaning'],
                         '남은 모호함: ' + assessment['remaining'],
                         '추가로 전달할 질문: ' + assessment['followup'], '']
    h.safe_path(root, '.harness/work/hr-outbox.md').write_text('\n'.join(rows), encoding='utf-8')


def inbox_status(root, state):
    file = h.safe_path(root, '.harness/work/hr-inbox.md')
    if not file.exists():
        return '답변함: 비어 있음'
    try:
        pending = stage_answers(state, file.read_bytes().decode('utf-8-sig'))
    except (h.KitError, OSError, UnicodeError) as exc:
        return '답변함: 확인 필요 · ' + str(exc)
    return '답변함: ' + ('미반영 원문 ' + ', '.join(qid for qid, _ in pending) if pending else '새 원문 없음')
