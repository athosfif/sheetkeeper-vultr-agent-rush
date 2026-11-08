# SheetKeeper — uma análise que vem com provas

## Estado atual em 8 de novembro de 2026

Preparação local da FIGUEIRA AI para Vultr Agent Rush, trilha C1 pretendida. O cupom oficial foi aceito em 08/11 e o painel confirmou US$ 200 de crédito, com vencimento em 09/12/2026, sem cadastro de cartão. A implantação Vultr, inferência real, demonstração pública e submissão continuam pendentes. Confirmar o prazo atual na página oficial antes do envio.

O núcleo inicial foi criado em 1 de outubro de 2026, antes da janela do evento. Essa origem deve ser declarada e sua elegibilidade de reutilização ainda precisa de confirmação. Os documentos históricos em `docs` descrevem a preparação daquela data. O plano atual está em [Verificação na Vultr](docs/VULTR-EXECUTION-PLAN.md).

O usuário carrega um CSV sintético, pede uma agregação, revisa o plano e libera sua execução em um sandbox descartável. O produto apresenta o gráfico, o código executado, hashes de entrada/código e o comprovante de destruição do ambiente.

## Material preparado

- [Arquitetura, decisões e limites](docs/ARQUITETURA.md)
- [Escopo e fluxo de produto](docs/PRODUTO.md)
- [Requisitos oficiais, fontes e preparação anterior ao evento](docs/REQUISITOS-E-FONTES.md)
- [Roteiro da demonstração e critérios de aceite](docs/DEMO-E-ACEITE.md)
- [Plano de implantação e custos](docs/IMPLANTACAO.md)
- Evidências históricas preservadas separadamente na preparação de 01/10. O pacote de código não inclui provas privadas de suporte ou dados de conta.

## Abrir localmente

Requer Python 3.12 ou superior. Sem dependências de aplicação ou chamadas pagas. Na raiz desta pasta:

```sh
PYTHONPATH=src python3 -m sheetkeeper.server --port 8767
```

Abra `http://127.0.0.1:8767`. Use **Usar exemplo sintético → Preparar plano**. O modo padrão é um plano fixo, identificado como ensaio sem IA. O plano não equivale a executar a análise.

Para executar ou testar a contenção, um daemon Docker Linux precisa estar disponível e a imagem precisa existir localmente:

```sh
docker build -t sheetkeeper-sandbox:prep sandbox
```

Isso baixa a base oficial Python se ela ainda não existir. A imagem foi construída e os testes reais no Docker local passaram em 01/10/2026. Nenhum código gerado tem fallback no Python do computador. Com Docker ausente, o plano continua revisável e a execução fica indisponível.

## Testes

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

A suíte verifica entrada/saída, rejeição de valores inconsistentes, envelope de integração Vultr com rede simulada, limites do processo de captura, preparação do comando Docker, estados de execução com runtime simulado, limpeza pendente, expiração de acesso, HTTP, origem, autorização e indisponibilidade de comprovantes antes de executar.

A suíte unitária passou em **23 testes**. O ensaio real no Docker local passou em **8 casos** de análise e limites, mais **3 ciclos da aplicação**: análise, contenção e recuperação. O resultado sintético foi comparado independentemente com o CSV; não restaram containers órfãos. Rede, leitura do host, usuário, raiz somente leitura, memória, processos, excesso de saída e saída por link simbólico foram verificados.

A revisão no navegador separado passou em **16 verificações**, incluindo inglês, português, espanhol, desktop, celular, teclado, persistência do idioma, download, erro, contenção e recuperação. As capturas históricas ficam na pasta preservada da preparação de 01/10, separada deste pacote público. Elas não comprovam execução atual na Vultr.

```sh
PYTHONPATH=src python3 scripts/check_docker.py
```

Essas verificações comprovam somente o ensaio no Docker Desktop local. **Inferência e implantação na Vultr, daemon rootless e limites na VM de produção continuam pendentes.** Ver `docs/DEMO-E-ACEITE.md`.

## Integração preparada

`.env.example` contém somente os nomes das configurações. O servidor não carrega `.env` automaticamente. Configure as variáveis no serviço da futura VM; nunca no navegador ou no repositório.

O adaptador usa a API oficial `https://api.vultrinference.com/v1/chat/completions`, tem timeout de 25 segundos e limite de 2.500 tokens de saída. Fica desativado por padrão. Modelo, disponibilidade, preço e compatibilidade da resposta devem ser revalidados no acesso atual do evento. A preparação não escolhe nem contrata uma assinatura.

Somente a pergunta, os nomes das colunas e a quantidade de linhas são enviados ao modelo no planejador atual. Resultados brutos e stderr não são enviados para reparo automático; esse fluxo ainda não existe nesta versão.

## Limites da versão

Registro em memória, 1 execução ativa, até 20 tarefas guardadas por uma hora, CSV de até 200 KB/2.000 linhas/24 colunas. Reiniciar o servidor perde os registros. O resultado tem verificações aritméticas e de contagem, mas ainda precisa de revisão semântica humana. Dados médicos, identificadores de pessoas e decisões clínicas não fazem parte da demonstração.

Material anterior ao evento deve ser declarado. A regra específica sobre reutilização precisa ser confirmada no regulamento/kickoff; o núcleo de IA, prova na Vultr e narrativa final devem ser construídos e registrados durante a janela autorizada.

Interface em inglês, português e espanhol, com seleção automática por preferência regional do navegador e troca manual. Números e datas usam Intl; CSV e evidências preservam os originais. Ver docs/PRODUTO.md.

## Alteração local de 06/11

Carregar exemplo ou arquivo bloqueia a preparação até terminar. Alterações na pergunta, planilha ou modo invalidam o plano anterior. Regressão de estado da interface verificada com `node tests/test-ui-state.cjs`. Os 23 testes Python foram repetidos na cópia atual com sucesso. A captura de interface do material é do fluxo local de revisão, com execução indisponível por ausência de Docker.
