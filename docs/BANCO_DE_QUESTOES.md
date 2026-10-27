# Seu banco de questões

O Concursinho inclui uma base inicial gratuita de **348 questões reais da FGV**, extraídas de oito provas públicas, com respostas conferidas nos respectivos gabaritos definitivos. São 12 disciplinas, incluindo Português, desenvolvimento, banco de dados e segurança. Essa base é um ponto de partida: não representa a cobertura completa do edital do TJPB.

Abra **Questões** no desktop ou no Android. O aplicativo funciona offline, sem conta nem assinatura.

## Praticar

- Sorteie livremente ou filtre por disciplina, tópico e banca.
- Escolha todas, ainda não respondidas ou questões cuja última resposta foi errada.
- Com “evitar repetições” ativo, percorra o conjunto em ordem aleatória antes de iniciar outro ciclo. Alterar os filtros reinicia esse ciclo. Desative a opção para sorteios independentes que podem repetir uma questão.
- Selecione uma alternativa e confirme. Pular não conta como tentativa; confirmar a mesma resposta novamente não duplica o registro.
- Depois de errar, indique o motivo: conteúdo, interpretação, distração, cálculo ou chute.

Os assuntos da base são uma **classificação sugerida**, não uma revisão pedagógica. Use “Ajustar assunto e tópico” para corrigir uma classificação; os indicadores anteriores acompanham a mudança. O retorno mostra o gabarito oficial. A base inicial ainda não possui comentários de resolução revisados.

No Android, o recorte do PDF preserva código, figuras e destaques. Também é possível ler o texto extraído e abrir a prova na página original. No desktop, consulte a prova pelo botão de origem e pela página indicada.

## Entender seu desempenho

O painel apresenta tentativas, acertos, questões distintas, evolução diária e motivos de erro informados por você. Filtre o diagnóstico por disciplina e período: todo o histórico, últimos 7 ou 30 dias.

O gráfico por assunto usa **a primeira resposta de cada questão dentro do período selecionado**, para reduzir a inflação dos acertos por repetição. Os totais de tentativas, a evolução diária e os motivos incluem todas as respostas do período. Por isso, os números podem ser diferentes.

Com menos de 10 questões distintas, o tópico aparece como “Amostra inicial”. A partir de 10, acerto de 80% ou mais é “Ponto forte”; abaixo de 60%, “Prioridade de revisão”; entre esses valores, “Em desenvolvimento”. São critérios orientativos, não uma previsão de aprovação. As recomendações usam regras locais e os motivos registrados, sem serviço de IA ou assinatura.

## Aumentar a base

Importe arquivos **JSON** ou **JSONL/NDJSON** pelo botão da interface. O aplicativo aceita de duas a cinco alternativas por questão. O JSON pode ser uma lista de objetos ou um objeto com `schemaVersion: 1` e `questions: [...]`. No JSONL, cada linha contém um objeto completo. Prefira JSONL para lotes grandes; no Android, JSON tem limite de 30 MB e JSONL é lido em fluxo.

Campos obrigatórios:

| Campo | Conteúdo |
|---|---|
| `id` | Identificador estável e único |
| `subject` | Disciplina |
| `topic` | Tópico |
| `stem` | Enunciado completo |
| `options` | Lista de 2 a 5 alternativas, em ordem |
| `answer` | Índice inteiro: **0 = A**, 1 = B, 2 = C, 3 = D, 4 = E |
| `source` | Identificação da prova ou origem |

Campos opcionais incluem `board`, `year`, `role`, `explanation`, `sourceUrl`, `answerSourceUrl` e `classification`. Marque `annulled: true` para excluir uma anulada do lote.

O lote é importado em uma transação: uma linha inválida cancela a importação inteira. IDs ou conteúdos já existentes são ignorados, sem substituir o gabarito anterior. A infraestrutura foi testada com **10 mil questões**; esse número é um teste de capacidade, não a quantidade entregue.

Não existe importação automática de qualquer PDF para questões. A ferramenta em `tools/build_question_bank.py` foi preparada para os modelos específicos de prova da base inicial. Adicionar provas de outros formatos exige adaptar a extração e conferir enunciados e gabaritos. Use materiais que você tenha autorização para armazenar; nenhuma plataforma paga foi copiada.

## Dados e cópias de segurança

O desktop grava `question-bank.sqlite3` na pasta do aplicativo. O Android usa um SQLite no diretório privado do app. Esses arquivos ficam fora do Git. O histórico do computador e o do celular são independentes; não há sincronização automática.

A exportação **CSV** contém indicadores, não uma cópia restaurável das respostas. No desktop, o botão de backup copia o SQLite completo. O JSON de marcações do checklist também não inclui o banco de questões. Desinstalar o Android ou limpar seus dados pode apagar o histórico; a versão atual ainda não oferece exportação completa desse banco pelo Android.

## Origem e verificação

O [relatório da extração](../data/question-bank-build.json) registra contagens, exclusões e hashes dos PDFs. O [catálogo de fontes](../mobile/assets/data/sources.json) e cada questão guardam as referências da prova e do gabarito. Foram excluídos itens anulados, conteúdos fora do recorte de TI, itens sem classificação e enunciados que dependiam de contexto externo não preservado. A classificação e a extração de texto podem conter falhas: confira o PDF original quando necessário.

A interface segue o visual existente de papel, verde e ocre, com o fluxo de resposta separado do diagnóstico. O recorte original é priorizado para evitar perder a formatação necessária à resolução.
