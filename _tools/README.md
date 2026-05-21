# _tools/ — scripts de manutenção

Scripts utilitários do projeto. **Rodar sempre a partir da raiz do repositório**
(ex: `python _tools/_cache_bust_hubs.py`), não de dentro de `_tools/`.

## Recorrente (rotina mensal)

| Script | Quando rodar |
|---|---|
| `_cache_bust_hubs.py` | Depois de todo fechamento mensal — adiciona `?v=AAAAMMDD` nos links dos Hubs pra forçar versão nova. Funciona de qualquer lugar (resolve a raiz via `__file__`). |

## Reutilizáveis (quando precisar)

| Script | Pra quê |
|---|---|
| `_fix_mobile_overflow.py` | Reaplica o pacote de CSS responsivo mobile em todos os portais |
| `_audit_auth.py` | Audita o estado de autenticação/gate dos portais |

## One-shot (já cumpriram a função — mantidos como histórico)

`_cleanup_orfaos_v3.py`, `_fix_auth_session.py`, `_fix_boot_spinner.py`,
`_fix_ux_pack1.py`, `_padroniza_headers.py`, `_reconstruir_abril_admins.py`,
`_propagar_visual_endo_individuais.py`, `_propagar_visual_oxy_individuais.py`,
`_propagar_visual_cirurgias_individuais.py`

Esses rodaram uma vez para uma migração/correção específica. Não precisam
rodar de novo. Se algum dia precisar reaproveitar a lógica, rode a partir
da raiz do repositório.
