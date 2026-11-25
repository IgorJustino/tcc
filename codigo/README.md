# Pipeline de reconstrução temporal

Protótipo do artefato do TCC: reconstituir o estado de tarefas usando somente
eventos que já estavam disponíveis em uma data de corte. O armazenamento registra
o horário declarado pela fonte (`occurred_at`), o recebimento pelo pipeline
(`received_at`) e o instante em que o evento normalizado tornou-se consultável
(`available_at`).

## Executar

O projeto usa apenas a biblioteca padrão do Python, inclusive para os testes:

```bash
cd codigo
python -m unittest discover -s tests -v
```

Exemplo de fluxo:

```bash
python -m temporal_reconstruction.cli init --database dados/replay.db
python -m temporal_reconstruction.cli ingest --database dados/replay.db --input dados/exemplo_eventos.json
python -m temporal_reconstruction.cli reconstruct --database dados/replay.db \
  --cutoff 2026-11-18T12:00:00Z --mode availability
```

`--mode occurrence` reproduz a estratégia ingênua: filtra apenas pela ocorrência.
`--mode availability` é a estratégia principal: só considera eventos já
consultáveis no instante de corte. A saída contém os IDs dos registros de origem,
permitindo rastrear cada estado reconstruído.

## Integração com o motor da dupla

O adaptador exporta uma rede diretamente compatível com as estruturas `Task` e
`ProjectNetwork` do motor Go, mantendo a proveniência em arquivo separado:

```bash
python -m temporal_reconstruction.cli export-network --database dados/replay.db \
  --cutoff 2026-11-19T12:00:00Z --mode availability \
  --template dados/exemplo_rede.json \
  --output dados/network.json --provenance-output dados/provenance.json
```

O contrato e a divisão de responsabilidades estão em
[`docs/contrato-integracao.md`](docs/contrato-integracao.md).

## Contrato de entrada

O comando `ingest` recebe uma lista JSON. Cada item precisa ter:

```json
{
  "source_event_id": "github-123",
  "task_id": "issue-42",
  "event_type": "task_started",
  "occurred_at": "2026-11-18T09:00:00Z",
  "received_at": "2026-11-18T09:02:00Z",
  "available_at": "2026-11-18T09:03:00Z"
}
```

Os tipos inicialmente aceitos são `task_created`, `task_started`,
`task_completed`, `task_reopened` e `task_cancelled`. A chave
`source_event_id` torna a ingestão idempotente.
