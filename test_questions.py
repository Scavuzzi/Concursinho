import json
import random
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from questions import QuestionBank,validate_question


def fixture(i,subject='Banco de dados',topic='SQL'):
    return {'id':f'test:{i}','subject':subject,'topic':topic,
            'stem':f'Enunciado fictício {i}?','options':[f'Certa {i}',f'Errada {i}'],
            'answer':0,'source':'Exclusiva para testes','board':'Teste'}


class QuestionBankTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'bank.sqlite3'
        self.bank=QuestionBank(self.path,random.Random(42))
        self.addCleanup(lambda:self.bank.close())

    def load(self,items):return self.bank.import_lines(map(json.dumps,items))

    def test_import_is_atomic_and_deduplicates_without_overwriting_answers(self):
        self.load([fixture(1)])
        result=self.load([{**fixture(1),'answer':1},{**fixture(1),'id':'different'},fixture(2)])
        self.assertEqual(result['added'],1)
        self.assertEqual(result['duplicates'],2)
        with self.assertRaises(ValueError):self.load([fixture(3),{'id':'invalid'}])
        self.assertEqual(self.bank.count(),2)
        self.assertTrue(self.bank.answer('test:1',0,'correct'))

    def test_random_cycle_and_filters(self):
        self.load([fixture(i) for i in range(20)]+[fixture(20,'Redes','TCP')])
        selected=set()
        for _ in range(20):
            q,restarted=self.bank.draw(subject='Banco de dados')
            self.assertFalse(restarted)
            self.assertNotIn(q['id'],selected)
            selected.add(q['id'])
        self.assertTrue(self.bank.draw(subject='Banco de dados')[1])
        self.assertEqual(self.bank.draw(subject='Redes',topic='TCP')[0]['id'],'test:20')
        self.assertIsNone(self.bank.draw(subject='Inexistente')[0])

    def test_optional_null_metadata_is_compatible_with_mobile(self):
        q={**fixture(1),'sourceUrl':None,'answerSourceUrl':None,'explanation':None}
        self.assertEqual(self.load([q])['added'],1)
        saved=self.bank.draw()[0]
        self.assertEqual(saved['sourceUrl'],'')
        self.assertEqual(saved['explanation'],'')

    def test_new_seed_revision_adds_questions_without_losing_history_or_user_tags(self):
        old=Path(self.temp.name)/'old.jsonl'
        old.write_text(json.dumps(fixture(1))+'\n',encoding='utf-8')
        self.bank.seed(old,revision='v1')
        self.bank.answer('test:1',1,'before-upgrade')
        self.bank.reclassify('test:1','Minha disciplina','Meu tópico')
        new=Path(self.temp.name)/'new.jsonl'
        new.write_text('\n'.join(json.dumps(q) for q in [fixture(1),fixture(2)]),encoding='utf-8')
        self.bank.seed(new,revision='v2')
        self.bank.seed(new,revision='v2')
        self.assertEqual(self.bank.count(),2)
        self.assertEqual(self.bank.report()['attempts'],1)
        self.assertEqual(self.bank.report()['topics'][0]['subject'],'Minha disciplina')

    def test_independent_mode_allows_repeats(self):
        self.load([fixture(1)])
        for _ in range(3):self.assertFalse(self.bank.draw(avoid_repeats=False)[1])

    def test_attempts_are_idempotent_and_first_answer_is_not_inflated(self):
        self.load([fixture(1)])
        self.bank.answer('test:1',1,'first')
        self.bank.answer('test:1',1,'first')
        self.bank.answer('test:1',0,'repeat')
        r=self.bank.report()
        self.assertEqual((r['attempts'],r['correct'],r['unique_questions']),(2,1,1))
        self.assertEqual(r['topics'][0]['correct'],0)
        self.assertIsNone(self.bank.draw(mode='errors')[0])
        self.assertIsNone(self.bank.draw(mode='unanswered')[0])

    def test_error_reasons_period_and_reclassification_follow_data(self):
        self.load([fixture(1)])
        self.bank.answer('test:1',1,'old',at=datetime.now(timezone.utc)-timedelta(days=45))
        self.bank.answer('test:1',0,'new')
        self.bank.tag_error('old','Interpretação')
        self.assertEqual(self.bank.report()['topics'][0]['dominant_reason'],'Interpretação')
        self.assertEqual(self.bank.report(7)['topics'][0]['correct'],1)
        self.bank.reclassify('test:1','Desenvolvimento','Algoritmos')
        self.assertEqual(self.bank.report()['topics'][0]['subject'],'Desenvolvimento')

    def test_reopen_preserves_draw_and_backup_preserves_history(self):
        self.load([fixture(1),fixture(2)])
        first,_=self.bank.draw()
        self.bank.answer(first['id'],1,'persist')
        backup=Path(self.temp.name)/'backup.sqlite3'
        self.bank.backup(backup)
        self.bank.close()
        self.bank=QuestionBank(self.path)
        self.assertNotEqual(self.bank.draw()[0]['id'],first['id'])
        restored=QuestionBank(backup)
        try:self.assertEqual(restored.report()['attempts'],1)
        finally:restored.close()

    def test_starter_bank_has_known_sources_valid_choices_and_no_cancelled_records(self):
        seed=Path(__file__).parent/'mobile/assets/data/questoes.jsonl'
        self.bank.seed(seed)
        count=self.bank.count()
        self.assertGreater(count,250)
        self.bank.seed(seed)
        self.assertEqual(self.bank.count(),count)
        for row in self.bank.db.execute('SELECT payload FROM questions'):
            q=validate_question(json.loads(row[0]))
            self.assertEqual(q['board'],'FGV')
            self.assertTrue(q['sourceUrl'].startswith('https://conhecimento.fgv.br/'))
            self.assertTrue(q['answerSourceUrl'].startswith('https://conhecimento.fgv.br/'))
            self.assertTrue(q['clips'])

    def test_large_bank_queries_ids_and_correct_filtered_question(self):
        self.load(fixture(i,'SQL' if i%2==0 else 'Redes') for i in range(10000))
        self.assertEqual(self.bank.count(),10000)
        for _ in range(8):self.assertEqual(self.bank.draw(subject='SQL')[0]['subject'],'SQL')


if __name__=='__main__':unittest.main()
