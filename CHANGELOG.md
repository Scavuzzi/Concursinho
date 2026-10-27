# Historico de mudancas

## 2026-10-27 — 1.2.0, novas fontes de TI

- Ampliada a base de 348 para 931 questões oficiais distintas, com 583 novas questões de 16 cadernos de TI e conferência nos gabaritos definitivos.
- Incluídas fontes MPU, CPRM, ALE-RO, MPES, MPRJ, São José dos Campos e TCE-RR; Dataprev continua excluída.
- Adicionados seleção explícita do cargo/tipo, manifesto com hashes, verificação integral dos registros e deduplicação entre especialidades.
- Preservados histórico e classificação pessoal ao atualizar a base; adicionados testes da atualização em Python e Dart.
- Atualizado o acervo Android para 25 provas e 45 PDFs; corrigido o total exibido na biblioteca.
- Disponibilizadas 62 questões autorais em arquivo opcional, sem incorporá-las à contagem oficial.
- Corrigida a aceitação de metadados opcionais nulos no importador desktop e a navegação do teste Android após rolagem.
- Corrigido o retorno aos controles de questões longas; teste Android completo aprovado com renderização nativa, resposta, gráficos, persistência e atualização da base.

## 2026-10-27 — 1.1.0, banco de questões

- Incluídas 348 questões reais da FGV, com referências e gabaritos definitivos, classificação sugerida e exclusão de anuladas e contexto incompleto.
- Adicionados SQLite, filtros, sorteio com ciclo opcional sem repetição, respostas, motivos de erro e diagnóstico no desktop e Android.
- Adicionados indicadores por primeira resposta no período, cautela para amostras pequenas, revisão e recomendações locais.
- Adicionadas importação JSON/JSONL com transação e deduplicação, edição de assunto e exportação CSV. Backup completo de SQLite disponível no desktop.
- Adicionado recorte original de PDF no Android e abertura na página de origem.
- Documentados formato de importação, limites e armazenamento em `docs/BANCO_DE_QUESTOES.md`.

## 2026-10-27 — consolidação e documentação

- Resolvidos os conflitos entre os históricos locais, preservando Android, TJPB, salvamento atômico e foco por disciplina.
- Removida a duplicação do carregamento de .env produzida pela mesclagem.
- Renovado o README com capa, capturas reais, configuração, leitura adaptada e instruções de desenvolvimento.
- Mantida uma única cópia ativa do projeto; o caminho antigo de Downloads passa a apontar para ela.

## 2026-10-26

- Adicionada aba TJPB 2026 com checklist, busca por assunto, provas e discursiva.
- Integrado o acervo do Obsidian sem copiar PDFs para o repositório.
- Separados gabaritos, marcações dos tópicos e provas resolvidas.
- Registrado o assunto do Pomodoro no início da sessão, preservando a atribuição ao trocar a seleção da biblioteca.
- Mantidos a biblioteca anterior, seu progresso e os arquivos locais de configuração.
- Adicionados testes do catálogo, progresso, portabilidade dos caminhos e continuidade do foco.


## 2026-08-08

- Corrigido o apontamento dos materiais para o vault do Obsidian.
- Os PDFs foram movidos de `D:\Desktop\ESTUDO\Concursinho\Materiais` para `D:\Documents\Segundo Cérebro\Projetos\Estudos\Concursinho\Materiais`.
- Restos de codigo que estavam no vault foram movidos para auditoria.

## 2026-07-27

- Criada distribuicao canonica em `D:\Desktop\ESTUDO\Concursinho`.
- Separados codigo (`App`) e PDFs (`Materiais`).
- Adicionado suporte a caminho relativo para a biblioteca.
- Adicionado botao para abrir o caderno do Concursinho no Obsidian.
- Mantidos gravacao atomica, recuperacao por backup e fluxo `Estudar agora`.
- Atualizado o atalho da area de trabalho para a nova distribuicao.


## 2026-10-26 — versão Android

- Adicionado projeto Flutter Android em `mobile/`, com dados e PDFs do TJPB disponíveis offline.
- Implementados leitor PDF nativo via PDFium, modo de texto, fontes locais, temas, margens, entrelinhas, suavização de luz e marcadores.
- Adicionados progresso local com recuperação, transferência de marcações em JSON e Pomodoro com retomada pelo horário.
- Aplicativo desktop e materiais arquivados da Dataprev preservados.
