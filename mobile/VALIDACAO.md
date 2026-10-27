# Validação da entrega Android — 26/10/2026

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
