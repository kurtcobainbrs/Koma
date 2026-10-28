# Estabilidade da interface no Windows

Os eventos 1000/1001 do Windows de 27/10/2026 registraram encerramentos em
`flutter_windows.dll`, com exceções `0xc0000005` e `0xc000041d`. Os símbolos do
PDB distribuído com o Flutter 3.44.8 identificaram os pontos como
`ui::AXNodeData::IsIgnored` e `ui::AXNode::GetNextUnignoredSibling`.

Os problemas [182444](https://github.com/flutter/flutter/issues/182444) e
[190357](https://github.com/flutter/flutter/issues/190357) do Flutter descrevem
atualizações órfãs na árvore de acessibilidade em Tooltips e Sliders dentro de
rotas/diálogos. A correção mantém o portal dos sliders em um overlay local e
coloca um limite explícito de semântica nas dicas, preservando o overlay da
janela para seu texto. A acessibilidade continua ativa.

`scripts/flet_compat.py` prepara uma cópia de compilação do Flet 1.0.5 em
`build/flet-compat`. Confere os hashes dos dois arquivos originais antes de
adaptar os pontos compartilhados de tooltip e slider. O SDK e o cache global
não são modificados. A implementação comum fica em
`flutter/compat/overlay_boundary.dart`; o comando habitual de compilação prepara
a dependência e inclui a correção na identidade do cache. As demais dependências
continuam fixadas nos lockfiles. Para trabalhar diretamente nos projetos Flutter,
execute primeiro `.venv/Scripts/python.exe scripts/build_flet_client.py`.

O teste `overlay_boundary_test.dart` inspeciona as atualizações serializadas de
semântica: o cenário original produz nós sem pai e o mesmo cenário isolado não.
Também verifica arraste do slider e passagem do mouse entre dicas em um diálogo.
Essa verificação não equivale a garantir ausência de qualquer falha nativa futura.
Remova esta adaptação quando a versão fixada do Flutter resolver os dois casos e
a regressão continuar passando sem a adaptação.

A navegação do animatic atualiza agulha e transporte dentro do mesmo quadro;
prévia, legendas e seleção só mudam ao atravessar um corte. Posições repetidas
no mesmo frame não enviam atualizações. A posição de soltura é aplicada antes de
encerrar o gesto. A preparação de legendas mantém apenas um trabalho em execução
e o pedido mais recente, evitando filas de renderização durante navegação rápida.
