"""Register selected local TI booklets and exact final-key sections.

Run before build_question_bank.py. Originals stay in the collection directory.
Only explicitly selected roles are included; Dataprev remains excluded.
"""
import argparse
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

import fitz

from build_question_bank import ROOT, MOBILE, answer_key, lines, plain


# source folder, proof glob, display title, exact distinguishing key heading
SELECTION = [
    ('mpu_2025', '*desenvolvimento*', 'MPU 2025 · Desenvolvimento de Sistemas', r'analista do mpu - desenvolvimento de sistemas - 1'),
    ('cprm_2025', '*sistemas*', 'CPRM 2025 · Análise e Desenvolvimento de Sistemas', r'analista em geociencias - analise e desenvolvimento de sistemas - 1 - turno manha'),
    ('alero_2025', '*cnsal25*', 'ALE-RO 2026 · Análise e Desenvolvimento de Sistemas', r'analista legislativo - tecnologia da informacao - analise e desenvolvimento de sistemas - 1 - turno tarde'),
    ('alero_2025', '*cnsal26*', 'ALE-RO 2026 · Banco de Dados', r'analista legislativo - tecnologia da informacao - banco de dados - 1 - turno tarde'),
    ('alero_2025', '*cnsal27*', 'ALE-RO 2026 · Infraestrutura de Redes', r'analista legislativo - tecnologia da informacao - infraestrutura de redes e comunicacao - 1 - turno tarde'),
    ('mpes_2026', '*analista_de_sistemas*', 'MPES 2026 · Analista de Sistemas', r'agente especializado – analista de sistemas - tipo 1 - turno manha'),
    ('mpes_2026', '*experiencia_do_usuario*', 'MPES 2026 · Experiência do Usuário', r'agente especializado – analista de experiencia do usuario – ux - tipo 1 - turno manha'),
    ('mpes_2026', '*analista_de_infraestrutura*', 'MPES 2026 · Infraestrutura', r'agente especializado – analista de infraestrutura - tipo 1 - turno manha'),
    ('mpes_2026', '*seguranca_da_informacao*', 'MPES 2026 · Segurança da Informação', r'agente especializado – analista de seguranca da informacao - tipo 1 - turno manha'),
    ('mpes_2026', '*cientista_de_dados*', 'MPES 2026 · Ciência de Dados', r'agente especializado – cientista de dados e inteligencia de negocios - tipo 1 - turno manha'),
    ('mpes_2026', '*engenheiro_de_dados*', 'MPES 2026 · Engenharia de Dados', r'agente especializado – engenheiro de dados - tipo 1 - turno manha'),
    ('mpes_2026', '*qualidade_e_testes*', 'MPES 2026 · Qualidade e Testes de Software', r'agente tecnico – qualidade e testes de software - tipo 1 - turno manha'),
    ('mprj_2025', '*cns102*', 'MPRJ 2025 · Tecnologia da Informação', r'analista do ministerio publico - area administrativa - tecnologia da informacao - 1'),
    ('prefsjc_2024', '*cns001*', 'São José dos Campos 2024 · Tecnologia da Informação', r'analista em gestao municipal \(tecnologia da informacao\) - tipo\s+1'),
    ('tce_rr_2025', '*cns401*', 'TCE-RR 2025 · Desenvolvimento de Sistemas', r'analista administrativo - tecnologia da informacao - desenvolvimento de sistemas - tipo\s+1'),
    ('tce_rr_2025', '*cns402*', 'TCE-RR 2025 · Banco de Dados', r'analista administrativo - tecnologia da informacao - banco de dados - tipo\s+1'),
]

KEY_NAMES = {
    'mpu_2025': 'gabarito_definitivo_mpu_2025.pdf',
    'cprm_2025': 'gabarito_definitivo_cprm_2025.pdf',
    'alero_2025': 'gabarito_definitivo_alero_2025.pdf',
    'mpes_2026': 'gabarito_definitivo_mpes_2026.pdf',
    'mprj_2025': 'gabaritodefinitivo09_09_mprjanalista.pdf',
    'prefsjc_2024': 'sjctecnologia2024_gabarito_definitivo_20240208.pdf',
    'tce_rr_2025': 'gabarito_definitivo_tcerr_auditor_e_analista_ap01.pdf',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(collection, apply=False):
    rows = list(csv.DictReader((collection/'documentos.csv').open(encoding='utf-8-sig')))
    catalog = json.loads((MOBILE/'assets/data/catalog.json').read_text(encoding='utf-8'))
    sources = json.loads((MOBILE/'assets/data/sources.json').read_text(encoding='utf-8'))
    planned = []
    for index, (folder, pattern, title, heading) in enumerate(SELECTION, 10):
        candidates = list((collection/'pdfs'/folder).glob(pattern+'.pdf'))
        if len(candidates) != 1:
            raise ValueError(f'{folder}/{pattern}: expected exactly one proof, got {candidates}')
        proof = candidates[0]
        key = collection/'pdfs'/folder/KEY_NAMES[folder]
        proof_row = next(r for r in rows if r['arquivo'].replace('\\','/') == str(proof.relative_to(collection)).replace('\\','/'))
        assert digest(proof) == proof_row['sha256'], f'Proof hash changed: {proof}'
        with fitz.open(proof) as doc:
            count = re.search(r'contendo\s+(\d+)', ' '.join(doc[0].get_text().split()), re.I)
            if not count:
                raise ValueError(f'Cannot establish objective count from cover: {proof}')
            question_count = int(count[1])
        with fitz.open(key) as doc:
            matches = [(i+1,t.strip()) for i,p in enumerate(doc) for t,_,_ in lines(p) if re.fullmatch(heading,plain(t).strip())]
            if len(matches) != 1:
                raise ValueError(f'Exact key section must be unique: {title}: {matches}')
            page, matched_heading = matches[0]
            answers = answer_key(doc[page-1], folder, heading)
            if len(answers) != question_count:
                raise ValueError(f'Key/cover mismatch: {title}: {len(answers)} vs {question_count}')
        key_rows = [r for r in rows if r['competition'].lower().replace('-','_') == folder and 'gabarito' in (r['url']+' '+r['description']).lower() and 'definitiv' in (r['url']+' '+r['description']).lower()]
        if folder == 'tce_rr_2025': key_rows = [r for r in key_rows if 'ap01' in r['url']]
        if folder == 'mprj_2025': key_rows = [r for r in key_rows if 'analista' in r['url']]
        if len(key_rows) != 1:
            raise ValueError(f'Ambiguous key URL: {title}: {key_rows}')
        year = int(re.search(r'20\d\d', title)[0])
        organ = {'prefsjc_2024':'SJC','tce_rr_2025':'TCERR'}.get(folder,folder.split('_')[0].upper())
        uid = f'{index:02}_{organ}_{year}_FGV'
        exam_id = 'exam:'+uid
        docs = {}
        source_records = []
        for kind,path,url in [('prova',proof,proof_row['url']),('gabarito_definitivo',key,key_rows[0]['url'])]:
            doc_id = uid+'_'+kind
            asset = 'assets/pdfs/'+(doc_id if kind=='prova' else 'fonte_'+folder+'_gabarito_definitivo')+'.pdf'
            docs[kind] = doc_id
            source_records.append({'folder':uid,'kind':kind,'url':url,'sha256':digest(path)})
            if apply:
                shutil.copy2(path,MOBILE/asset)
                if not any(d['id']==doc_id for d in catalog['documents']):
                    catalog['documents'].append({'id':doc_id,'title':('Prova' if kind=='prova' else 'Gabarito definitivo')+' · '+title,'asset':asset,'kind':kind,'initialPage':1 if kind=='prova' else page,'examId':exam_id})
        if apply and not any(e['id']==exam_id for e in catalog['exams']):
            catalog['exams'].append({'id':exam_id,'title':title,'description':'FGV · Tipo 1 · fonte adicional de TI','documents':docs,'questionBank':{'keyHeading':heading,'questions':question_count}})
        if apply:
            for source in source_records:
                if not any(s['folder']==uid and s['kind']==source['kind'] for s in sources['exams']):sources['exams'].append(source)
        planned.append({'id':uid,'title':title,'objectiveQuestions':question_count,'keyPage':page,'keyHeading':matched_heading,'proofSha256':digest(proof),'keySha256':digest(key),'sources':source_records})
    if apply:
        for path,data in [(MOBILE/'assets/data/catalog.json',catalog),(MOBILE/'assets/data/sources.json',sources),(ROOT/'data/additional-question-sources.json',{'revision':'2026-10-27-v2','selected':planned,'excluded':'Dataprev and roles outside the selected TI scope; authorial questions remain a separate optional import.'})]:
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(planned,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('collection',type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    prepare(args.collection,args.apply)
