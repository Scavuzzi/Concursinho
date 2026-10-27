# Concursinho

Painel local para acompanhar PDFs de estudo e pomodoros.

O botao **Estudar agora** seleciona a disciplina recomendada, abre o proximo PDF
e inicia o Pomodoro em uma unica acao.

## Organizacao recomendada

- O codigo fica fora do Obsidian, em `D:\Desktop\ESTUDO\Concursinho\App`.
- Os materiais de estudo ficam no vault do Obsidian.
- Cada PC configura o proprio caminho local dos PDFs em `.env` ou pela aba `Configuracoes` do app.
- Estado local como `config.json`, `progresso.json`, `historico.json`, logs e ambiente virtual fica fora do Git.

## Configurar materiais

O arquivo `.env` deve apontar para a arvore de materiais no Obsidian:

```env
CONCURSINHO_MATERIAIS_PATH=D:\Documents\Segundo Cérebro\Projetos\Estudos\Concursinho\Materiais
```

A pasta configurada deve conter uma subpasta por disciplina, com os PDFs dentro.

## Abrir PDFs

O comando padrao para abrir PDFs e `auto`. Nesse modo o app usa o programa
padrao do sistema:

- Windows: abre com o app associado ao PDF.
- Linux: usa `xdg-open`.
- macOS: usa `open`.

## Rodar

```powershell
python main.py
```

Ou use `Abrir Concursinho.cmd`.

## Validar

```powershell
python -m unittest -v test_main.py
```


## TJPB 2026 — Desenvolvimento de Sistemas

A aba `TJPB 2026` abre por padrão e reúne o conteúdo deste concurso:

- 146 tópicos do edital em 14 blocos, com busca, filtro e marcação de estudo;
- nove provas anteriores, gabaritos definitivos separados e dois espelhos;
- orientações para a discursiva, plano completo e fontes no Obsidian;
- acesso ao edital retificado e à nota da retificação publicada em 26/10/2026;
- início de foco TJPB usando o mesmo Pomodoro, com a disciplina registrada no histórico.

Os 93 PDFs Dataprev foram retirados da biblioteca ativa em 26/10/2026 e preservados em `Arquivo - Dataprev 2024 - 2026-10-26`, ao lado de `Materiais` no Obsidian. As abas `Estudo` e `Revisão` continuam disponíveis para novos materiais. As provas não
entram na recomendação automática de aulas; os gabaritos são abertos apenas
pelo botão correspondente. Marcar uma prova como resolvida é independente de
marcar os tópicos estudados.

A pasta é localizada ao lado de `Concursinho` no cofre: a partir de
`Estudos/Concursinho/Materiais`, o app procura `Estudos/TJPB 2026`.
Se os arquivos estiverem em outro lugar, configure `CONCURSINHO_TJPB_PATH`
no `.env`. Os caminhos absolutos antigos do manifesto de downloads são
ignorados; os PDFs são localizados na pasta atual do cofre.

Os arquivos permanecem no Obsidian. As marcações do app ficam em
`tjpb-progresso.json`, fora do Git e separadas do progresso da biblioteca.
As caixas das notas Markdown não são sincronizadas com essas marcações.
O botão `Atualizar materiais` relê as notas e o catálogo sem redefinir o progresso.

Validação da integração:

```powershell
python -m unittest -v test_main.py test_tjpb.py
```


## Android

A pasta `mobile/` contém o aplicativo Android com os mesmos 146 tópicos e o
acervo TJPB, leitor PDF integrado e modo Leitura com fontes e aparência
ajustáveis. Não inclui os materiais Dataprev. A documentação de compilação,
instalação e transferência manual de progresso está em [mobile/README.md](mobile/README.md).

O desktop continua independente. O JSON de marcações tem o mesmo formato nos
dois aplicativos; preferências do leitor e PDFs importados ficam no aparelho.
