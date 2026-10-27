"""Check shipped records, official answer keys, source hashes and PDF bounds."""
import json
import sys
from collections import Counter

import fitz

from build_question_bank import ROOT, MOBILE, answer_key, src_hash

sys.path.insert(0, str(ROOT))
from questions import fingerprint, validate_question  # noqa: E402


def verify():
    catalog = json.loads((MOBILE/'assets/data/catalog.json').read_text(encoding='utf-8'))
    sources = json.loads((MOBILE/'assets/data/sources.json').read_text(encoding='utf-8'))['exams']
    records = [validate_question(json.loads(line)) for line in (MOBILE/'assets/data/questoes.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    report = json.loads((ROOT/'data/question-bank-build.json').read_text(encoding='utf-8'))
    assert len(records) == report['included']
    assert len({q['id'] for q in records}) == len(records)
    assert len({fingerprint(q) for q in records}) == len(records)
    documents = {d['id']: d for d in catalog['documents']}
    keys = {}
    pdfs = {}
    try:
        for index, exam in enumerate(catalog['exams']):
            if index >= 8 and not exam.get('questionBank'): continue
            folder = exam['id'].removeprefix('exam:')
            for kind in ('prova','gabarito_definitivo'):
                doc = documents[exam['documents'][kind]]
                path = MOBILE/doc['asset']
                source = next(s for s in sources if s['folder']==folder and s['kind']==kind)
                assert src_hash(path) == source['sha256'], str(path)
                pdfs[doc['id']] = fitz.open(path)
            key = documents[exam['documents']['gabarito_definitivo']]
            keys[folder] = answer_key(pdfs[key['id']][key['initialPage']-1],folder,exam.get('questionBank',{}).get('keyHeading'))
        for q in records:
            folder, number = q['id'].split(':tipo1:q')
            letter = keys[folder][int(number)]
            assert letter != '*' and q['answer']==ord(letter)-65, q['id']
            assert q['board']=='FGV' and q['sourceUrl'].startswith('https://conhecimento.fgv.br/'), q['id']
            assert q['answerSourceUrl'].startswith('https://conhecimento.fgv.br/'), q['id']
            assert q['clips'], q['id']
            if int(folder.split('_')[0]) >= 10:
                text_lines = [' '.join(t.lower().split()) for s in [q['stem'],*q['options']] for t in s.splitlines()]
                assert 'fgv conhecimento' not in text_lines and 'ministério público da união' not in text_lines, q['id']
            for clip in q['clips']:
                pdf = pdfs[q['documentId']]
                assert 1 <= clip['page'] <= len(pdf), q['id']
                rect = fitz.Rect(clip['rect'])
                assert not rect.is_empty and pdf[clip['page']-1].rect.contains(rect), q['id']
        print(json.dumps({'verifiedQuestions':len(records),'verifiedExams':len(keys),'subjects':dict(Counter(q['subject'] for q in records)),'checks':['unique IDs/content','source SHA-256','exact role/type final keys','non-annulled answers','PDF page/clip bounds']},ensure_ascii=False,indent=2))
    finally:
        for pdf in pdfs.values():pdf.close()


if __name__=='__main__':verify()
