"""Cleanup CIRÚRGICO — substitui APENAS a string exata órfã do v7→migração.

Estratégia segura: usa string-match literal (não regex genérico) que NÃO
pode acidentalmente pegar chaves do JS porque o padrão exato só existe
no fim do bloco v7 no <style>.

Padrão órfão a remover (entre o fim do v7 e o início do CSS original):
```
}

}

  .header-action-btn span{display:none;}
}
```

Pode ter variações com espaços/linhas em branco. Vou tentar 3 variantes
literais.
"""
import os, glob

# Variantes do padrão exato órfão (depois do fim do v7)
# Variante 1: tipo recebimento.html / produtividade (ambos com extra \n)
PADRAO_ORFAO_V1 = """
}

}

  .header-action-btn span{display:none;}
}




"""

PADRAO_ORFAO_V2 = """
}

}

  .header-action-btn span{display:none;}
}


"""

PADRAO_ORFAO_V3 = """
}

}

  .header-action-btn span{display:none;}
}
"""

SUBSTITUIR_POR = "\n"  # uma única linha em branco

def aplicar(arq):
    with open(arq, 'r', encoding='utf-8') as f:
        html = f.read()
    if '/* fix-mobile-overflow-v7 */' not in html:
        return 'SEM_V7', 0
    original = html
    delta = 0
    # Tenta as 3 variantes (do mais específico pro menos)
    for pad in (PADRAO_ORFAO_V1, PADRAO_ORFAO_V2, PADRAO_ORFAO_V3):
        if pad in html:
            html = html.replace(pad, SUBSTITUIR_POR, 1)
            delta = len(original) - len(html)
            break
    if html == original:
        return 'PADRAO_NAO_CASOU', 0
    with open(arq, 'w', encoding='utf-8', newline='') as f:
        f.write(html)
    return 'OK', delta

all_files = []
for f in glob.glob('*.html'): all_files.append(f)
for sub in ['oxy', 'cirurgias', 'hub', 'produtividade', 'oxy-produtividade',
            'dashboard-insights', 'admin', 'previas', 'atendimentos', 'fotona',
            'gestao-administrativa', 'dashboard-operacional', 'login']:
    if os.path.isdir(sub):
        for f in glob.glob(f'{sub}/*.html'): all_files.append(f)

stats = {}
total_bytes = 0
for arq in sorted(all_files):
    try:
        status, delta = aplicar(arq)
    except Exception as e:
        print(f'  ERRO {arq}: {e}')
        continue
    stats[status] = stats.get(status, 0) + 1
    total_bytes += delta

print(f'Stats: {stats}')
print(f'Bytes removidos: {total_bytes}')
