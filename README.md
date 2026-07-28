# Concursinho

Painel local para acompanhar PDFs de estudo e pomodoros.

O botão **Estudar agora** seleciona a disciplina recomendada, abre o próximo PDF
e inicia o Pomodoro em uma única ação. Enquanto houver uma sessão em andamento,
ele fica bloqueado para não trocar a matéria contabilizada no meio do ciclo.

## Organizacao recomendada

- O codigo fica neste repositorio e vai para o GitHub.
- Os materiais de estudo ficam fora do repositorio, de preferencia no vault do Obsidian.
- Cada PC configura o proprio caminho local dos PDFs em `.env` ou pela aba `Configuracoes` do app.
- Estado local como `config.json`, `progresso.json`, `historico.json`, logs e ambiente virtual fica fora do Git.
- Cada alteração de estado é gravada de forma atômica e mantém uma cópia `.bak` válida para recuperação automática.

## Preparar ambiente

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

No Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Depois da preparação, também é possível iniciar com dois cliques em
`Abrir Concursinho.cmd`.

Na distribuição em `D:\Desktop\ESTUDO\Concursinho`, o aplicativo fica em
`App` e os PDFs ficam na pasta irmã `Materiais`. O caminho relativo
`..\Materiais` evita acoplar a execução a uma letra de unidade específica.

O botão **Abrir caderno no Obsidian** abre a nota
`Projetos/Estudos/Concursinho` no vault `Segundo Cérebro`. O Obsidian guarda
anotações e revisões; conclusão de PDFs e Pomodoros continuam sendo controlados
por este aplicativo.

## Configurar materiais

Crie um arquivo `.env` a partir do exemplo:

```env
CONCURSINHO_MATERIAIS_PATH=D:\Caminho\Do\Seu\Vault\Materiais
```

A pasta configurada deve conter uma subpasta por disciplina, com os PDFs dentro.

## Abrir PDFs

O comando padrao para abrir PDFs e `auto`. Nesse modo o app usa o programa padrao do sistema:

- Windows: abre com o app associado ao PDF.
- Linux: usa `xdg-open`.
- macOS: usa `open`.

Se quiser forcar um leitor especifico, altere `Comando PDF` nas configuracoes. Use `{file}` onde o caminho do PDF deve entrar, por exemplo:

```text
zathura {file}
```

## Rodar

```bash
python main.py
```

No Linux, tambem da para usar:

```bash
./run.sh
```

## Validar

```bash
python -m unittest -v test_main.py
```

## Congelamento de manutenção

As funcionalidades ficam congeladas de **22/07/2026 a 06/08/2026**. Nesse
período, só justificam alteração falhas que impeçam abrir o aplicativo, abrir os
PDFs, iniciar o foco ou salvar o progresso. Ideias de melhoria ficam para revisão
após o período de uso real.
