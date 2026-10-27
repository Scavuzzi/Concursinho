# Concursinho — Android

Aplicativo Flutter instalado por APK, com renderização nativa de PDF via PDFium/pdfrx. Não depende de um servidor Python, de navegador externo ou de login.

## O que está incluído

- Versão 1.1.0: aba Questões, com 348 questões reais da FGV, filtros, sorteio, histórico, motivos de erro e gráficos locais. Importação JSON/JSONL e ajuste de classificação. Veja o [guia do banco](../docs/BANCO_DE_QUESTOES.md).
- Checklist TJPB: 146 tópicos em 14 blocos, com busca e progresso local.
- Nove provas, nove gabaritos definitivos e dois espelhos, separados. Edital consolidado e primeira retificação: 22 PDFs no APK.
- Leitor Original: páginas com zoom, navegação e filtros claro/sépia/noite.
- Modo Leitura: texto extraído por página, três fontes locais, tamanho 14–34, entrelinhas, margens, alinhamento e suavização da luz.
- Retomada por documento, marcadores de página e importação de PDF pelo seletor do Android.
- Pomodoro com retomada pelo horário ao voltar ao app. Não há alarme de término quando o Android suspende ou fecha o aplicativo.
- Exportação/importação de marcações em JSON. O formato de lista é compatível com `tjpb-progresso.json` do aplicativo desktop. A transferência é manual; não há sincronização automática.

PDF é um formato de página fixa: a troca de fonte atua no modo Leitura, sem alterar o arquivo. Páginas escaneadas não ganham texto sem OCR. A extração pode alterar a ordem de colunas; tabelas, código, figuras e alternativas devem ser conferidos em Original. Nenhum PDF da Dataprev foi incluído.

## Instalar

Android 7.0/API 24 ou superior. Copie o APK para o aparelho, abra o arquivo e autorize a instalação por esse gerenciador quando o Android solicitar. O acervo funciona sem internet. O aplicativo não pede acesso amplo ao armazenamento: a importação usa o seletor de arquivos do Android.

O APK é para instalação pessoal e usa a assinatura local de desenvolvimento gerada pelas ferramentas Android. Preserve a chave local se precisar produzir atualizações com a mesma assinatura. Esta entrega não publica o aplicativo na Play Store.

## Dados

As marcações, preferências e páginas ficam no diretório privado do aplicativo, em JSON com cópia de recuperação. Os PDFs importados são copiados para esse diretório. Desinstalar o app pode apagar esses dados: exporte as marcações se quiser transportá-las. O JSON de marcações não contém os PDFs importados nem as preferências do leitor.

Questões e respostas usam SQLite no diretório privado. O CSV exporta indicadores, sem restaurar o histórico. Não há sincronização com o computador nem backup completo do banco pela interface Android nesta versão.

## Compilar e verificar

Flutter 3.44 / Dart 3.12; Android SDK 36, NDK 28.2.13676358; Gradle 9.1; JDK 25 usado neste computador. Dependências resolvidas em `pubspec.lock`. O app desktop permanece separado.

```powershell
flutter pub get
flutter analyze
flutter test
flutter build apk --release
```

Teste Android com PDF real:

```powershell
flutter drive --driver=test_driver/integration_test.dart --target=integration_test/app_test.dart -d emulator-5580
```

A captura automática do Flutter usada neste emulador não inclui a imagem assíncrona do `PdfViewer`. O teste verifica os pixels produzidos pelo renderizador nativo; a página Original do APK release também é conferida por captura do próprio Android, separadamente. As capturas locais ficam em `test_artifacts/` (ignoradas pelo Git).

## Interface

Direção: caderno editorial, com fundo de papel, verde profundo e acento ocre. DM Sans na navegação; Source Serif na leitura; JetBrains Mono como alternativa. Ritmo de espaçamento 8/16/24, transições discretas e controles de toque do Material. O contraste entre a tipografia editorial e o progresso em verde dá identidade às telas. DFII: impacto 4 + adequação 5 + viabilidade 5 + desempenho 4 − risco 3 = 15.

## Fontes e licenças

As fontes vieram de `google/fonts`, sob SIL Open Font License; as licenças acompanham o aplicativo em `assets/licenses`. Os PDFs foram baixados dos portais oficiais da FGV, salvo as cópias históricas TJPB/FAPERP do EstudeGrátis. São materiais de estudo; as provas antigas não substituem o programa e as retificações atuais. O acervo corresponde à revisão de 26/10/2026.

As dependências de terceiros e suas licenças aparecem em “Sobre este acervo”. pdfrx usa PDFium e suas dependências. Nenhum serviço pago ou conta externa foi criado.
