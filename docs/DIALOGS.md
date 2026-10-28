# Ações de diálogos

`ui.design.dialog` aplica a apresentação comum e delega a `ui.dialog_actions.action_dialog` os contratos de interação. Cada formulário informa sua função `on_confirm` e, quando necessário, `on_cancel` e `on_outside`. A lógica não depende do texto ou da posição dos botões.

- Enter chama a ação de confirmação, inclusive nos campos de uma linha.
- Esc chama a ação de cancelamento.
- Campos multilinha preservam Enter para novas linhas.
- Clicar fora cancela por padrão nos diálogos não modais. O seletor de cores fornece `on_outside=apply`, confirmando a cor atual.
- Diálogos informativos fecham com Enter ou Esc.
- Uma escolha sem ação padrão explícita usa `on_confirm=False`; Enter não adivinha uma opção nem autoriza substituir arquivos.
- O animatic preserva seu tratamento de gestos e atalhos, usando `native_actions=False`.

O adaptador `flutter/koma_drop/lib/dialog_actions.dart` distingue teclado e clique externo antes do fechamento, sem depender de atrasos ou da animação do diálogo. As ações compartilham a proteção contra chamadas simultâneas, e o seletor de cores finaliza uma única vez. O cliente nativo precisa ser recompilado quando esse adaptador muda; o instalador já publicado não é atualizado automaticamente.
