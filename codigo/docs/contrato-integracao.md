# Contrato de integração: reconstrução temporal → motor de simulação

Este contrato separa explicitamente as responsabilidades dos trabalhos que usarão o
mesmo repositório de implementação no TCC2.

| Componente | Responsabilidade |
| --- | --- |
| Extrator de dados | Coletar eventos e parâmetros históricos de fontes GitHub/Git. |
| Reconstrução temporal (este módulo) | Persistir os três tempos, reconstruir o estado em um corte e registrar a proveniência do resultado. |
| Motor de simulação | Consumir a rede de tarefas já reconstruída e calcular CPM/Monte Carlo. |

## Invariantes da reconstrução

Cada evento possui `occurred_at <= received_at <= available_at`, em UTC. Para um
corte `t_c`, o modo `availability` só utiliza eventos cujo `available_at <= t_c`.
O arquivo de proveniência deve indicar o `source_event_id` que determinou o estado
de cada tarefa exportada.

## Entrada: modelo de rede

O exportador recebe um JSON com o formato abaixo. Os campos de cada tarefa são os
mesmos do `Task` em `Codigo/poc-engine/model.go` da dupla. `source_task_id` é um
campo exclusivo deste adaptador e faz a associação com `task_id` dos eventos.

```json
{
  "status_date": 5.0,
  "tasks": [
    {
      "id": "T1",
      "source_task_id": "github-issue-42",
      "name": "Implementar replay",
      "to": 1.0,
      "tm": 2.0,
      "tp": 4.0,
      "actual_duration": 0.0
    }
  ],
  "dependencies": [{"from": "T1", "to": "T2"}],
  "risks": []
}
```

## Saídas

- `network.json`: contrato direto do motor Go: `tasks`, `dependencies`, `risks` e
  `status_date`. Cada tarefa contém `id`, `name`, `to`, `tm`, `tp`, `progress`,
  `actual_duration` e `completed`.
- `provenance.json`: artefato exclusivo da reconstrução temporal, com o corte, o
  modo, a versão do contrato e o evento-fonte aplicado a cada tarefa.

O estado `completed` gera `progress = 1.0` e `completed = true`. Os estados
`open` e `in_progress` não autorizam inferir percentual de progresso: ambos são
exportados com `progress = 0.0`, até que uma fonte de checklist ou medição de
progresso seja integrada. Isso evita fabricar evidência para o simulador.

