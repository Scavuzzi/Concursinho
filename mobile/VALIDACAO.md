# Validação da entrega Android

## Versão 1.2.0 — 27/10/2026

- Base ampliada para 931 questões oficiais distintas de 24 cadernos, com 583 novas questões. Biblioteca com 25 provas e 45 arquivos PDF; nenhum Dataprev incluído.
- Verificação integral por `tools/verify_question_bank.py`: gabaritos definitivos do cargo/tipo correto, hashes dos PDFs, IDs e conteúdos únicos, páginas e limites dos recortes.
- 26 testes Python e 21 testes Flutter aprovados; analisador Dart sem problemas. Corrigido o preparo assíncrono do teste de navegação para o catálogo maior.
- Simulação com a base real da versão anterior: atualização de 348 para 931 registros preservou resposta e classificação pessoal. Testes de revisão da base também cobrem Python e Dart.
- Lote de 62 questões autorais validado e mantido como importação opcional, sem compor a contagem oficial.
- Teste integrado Android aprovado em Android 14/API 34: renderização PDFium com pixels reais do recorte, resposta incorreta, motivo, diagnóstico, persistência após reabertura e importação idempotente da base completa preservando a tentativa existente.
- Corrigido o retorno ao topo em questões longas, mantendo os controles na árvore de rolagem. A execução direta do teste dispensa a conexão instável do driver e usa o controlador externo correto.
- Compilação do APK final: em andamento.

## Versão 1.1.0 — 27/10/2026

- APK release compilado: 88.249.868 bytes; pacote `br.com.andre.concursinho`, versionCode 2, Android mínimo API 24.
- Assinatura v2 validada por apksigner; arquivo ZIP sem erro CRC, 22 PDFs e 348 questões. JSONL incluído idêntico ao arquivo fonte.
- SHA-256: `dafb0c2187fc4f6f8024f790364e000f30a30a6ba1b7cd876b605fa866763667`.
- Cópias `Concursinho-Android-1.1.0.apk` em Downloads e no Obsidian conferidas por hash.
- Analisador Dart sem problemas; 20 testes Flutter aprovados, incluindo SQLite, importação atômica, 10 mil registros e fluxo de resposta/diagnóstico em tela estreita. Desktop: 25 testes Python aprovados.
- A primeira execução do teste integrado de questões no emulador falhou por estado de rolagem no ExpansionTile. A chave foi corrigida, assim como a navegação do teste; o fluxo passou depois em teste de widget. O teste integrado nativo de questões não foi repetido após a correção. A renderização do recorte havia sido verificada por pixels nativos na execução anterior à falha.
- A primeira compilação release coincidiu com testes que regeneraram o registro de plugins e falhou. A compilação foi repetida após os testes e terminou com sucesso.
- Este APK não foi instalado em aparelho físico nem passou por nova sessão manual de uso no emulador. Os registros abaixo se referem à versão 1.0.0.

## Versão 1.0.0 — 26/10/2026

APK pessoal 1.0.0, 87.109.094 bytes (83,1 MiB), Android 7.0/API 24 ou superior.

SHA-256: `5052f608969ef8d82dcc26ffcd95065c5c7d8176b337e50e7700ea7813ea0651`.

- Compilação release concluída; assinatura APK verificada com apksigner (v2).
- APK instalado e aberto no emulador Android 14/API 34 x86_64.
- Tela Original conferida no APK release por captura Android: capa da prova TJRR 2024 renderizada, com texto, figuras e diagramação. Imagem local: `test_artifacts/release-original.png`.
- Análise Dart de lib, test, integration_test e test_driver: sem problemas.
- Oito testes de unidade/widget aprovados: catálogo, marcações, persistência, recuperação, preferências, foco, importação inválida e navegação em tela estreita.
- Teste integrado Android aprovado: rasterização nativa real (26.300 pixels de tinta na amostra), extração de texto, navegação, marcador, fonte DM Sans, tamanho aumentado, tema sépia, persistência e retorno à biblioteca.
- ZIP do APK sem erro CRC; 22 PDFs presentes, idênticos aos arquivos de origem por hash; nenhum arquivo Dataprev. Bibliotecas arm64-v8a, armeabi-v7a e x86_64 incluídas.
- Cópias em Downloads e no Obsidian conferidas com o mesmo SHA-256.

A captura de superfície do Flutter deixou a imagem assíncrona do PDF em branco no emulador. A verificação foi separada: pixels reais do renderizador no teste integrado e captura do próprio Android no APK release. O arquivo de instalação exibiu a página normalmente. Nenhuma alteração de código do aplicativo foi necessária após a compilação release.

O teste ocorreu em emulador; não foi realizada instalação em um aparelho físico. Os limites de extração de texto, transferência manual de marcações e alarme do Pomodoro estão descritos no README e no guia do Obsidian.
