# Diretrizes permanentes do projeto

- Manter o código modular, com responsabilidades e contratos claros entre modelo, comandos, interface e persistência.
- Implementar comportamentos reutilizáveis como funções ou componentes compartilhados. Os pontos de uso devem fornecer ações, parâmetros ou dados, sem repetir a lógica.
- Não identificar ações por textos de botões, títulos, posições fixas ou identificadores específicos. Usar capacidades, contratos e configurações explícitas.
- Evitar hardcode de regras de negócio e soluções especiais por tela. Centralizar constantes de interface e limites do modelo nos módulos responsáveis, seguindo os padrões existentes.
- Preservar a integridade dos documentos, o histórico e a compatibilidade ao alterar contratos ou formatos de salvamento.
- Manter a interface compacta, sem animações, priorizando a visualização do conteúdo.
- Usar textos de interface claros, curtos e diretos. Nomear ações pelo que fazem, manter os termos consistentes e incluir explicações apenas quando ajudarem no uso, evitando jargão, redundância e abreviações ambíguas.
- Não executar testes manuais sem solicitação do usuário. Usar apenas verificações automatizadas pontuais e relevantes; evitar suítes exaustivas sem necessidade.
- Cada node é a fonte única de verdade dos seus dados. Todas as suas propriedades, camadas e alterações devem pertencer à sua própria estrutura, sem armazenamento paralelo baseado em referências ao node. A interface apenas apresenta e modifica esses dados. Estado temporário de interface, como foco, ferramenta ativa ou gesto em andamento, deve ficar separado e não se tornar outra fonte dos dados do node.
- Canvas, timeline, propriedades e exportação devem consumir os mesmos dados do modelo, sem manter cópias autoritativas divergentes.
- Separar prévia de confirmação: durante um gesto, apresentar uma alteração temporária; ao confirmar ou soltar, registrar a alteração no modelo e no histórico. Cancelar deve descartar a prévia e preservar os dados confirmados.
- Priorizar a fluidez da usabilidade, inclusive no primeiro movimento e nas trocas de ferramenta. Não bloquear a interface. Operações pesadas devem ocorrer fora dos eventos do mouse e do fluxo de interação; durante gestos, atualizar apenas o necessário, sem reconstruir ou atualizar o canvas inteiro quando apenas controles locais mudarem.
- Versionar mudanças no formato dos documentos, com migrações explícitas, validação dos dados e proteção dos projetos anteriores.
- Direcionar verificações automatizadas às integrações críticas afetadas: salvar e abrir, copiar entre projetos, desfazer e refazer e exportar. Não ampliar a bateria sem uma necessidade concreta.
- Concluir o fluxo completo de cada função nova, considerando atalhos, confirmação, cancelamento, persistência, histórico e exportação quando aplicável.
- Definir limites claros para arquivos, pontos de desenho e consumo de memória nos módulos responsáveis, com mensagens compreensíveis quando atingidos.
- Registrar falhas com informações úteis para diagnóstico e reprodução, sem expor imagens, textos, áudios ou outros conteúdos dos projetos nos logs.
- Reaproveitar os componentes, o processo de release e o cache de compilação existentes. Evitar reconstruir ou repetir etapas que continuam válidas.
