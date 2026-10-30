# Caminho para uma versão estável

Prioridades após a prévia v0.3.0, em ordem. Esta lista distingue validações pendentes de defeitos já reproduzidos; não afirma que todos esses cenários apresentam falhas.

1. **Validar o fluxo completo de grupos em uso real.** Criar, entrar, voltar, desconectar, reconectar, aninhar e mover quadros entre grupos pela timeline. Conferir os avisos e a correspondência entre canvas, animatic e exportação. A validação manual fica com o usuário.
2. **Consolidar a proteção dos projetos.** Cobrir com verificações automatizadas dirigidas a abertura/migração de projetos representativos, salvar/reabrir, recuperação e desfazer/refazer após operações entre grupos. Verificar que mídias e desenhos desconectados continuam no arquivo e que salvamentos interrompidos preservam o arquivo anterior.
3. **Fixar uma referência de desempenho.** Registrar o tempo e a quantidade de atualizações do primeiro gesto, troca de ferramenta, mudança de modo e edição de timeline em projetos representativos. Manter as proteções de eventos reais do Flet contra travessias de mídia e atualizações amplas durante gestos. Investigar qualquer piora antes de incorporar novas funções.
4. **Homologar o pacote Windows.** Ainda está pendente verificar instalador e portátil em Windows limpo, sem Python/Blender, incluindo abertura offline, atualização, desinstalação, arraste externo e diferentes escalas de tela. O diagnóstico automatizado do pacote é uma verificação separada e não substitui essa homologação.
5. **Conferir mídias e exportações representativas.** Usar arquivos de imagem, vídeo e áudio de trabalho, grupos incompletos, proporções distintas e intervalos de exportação. Comparar duração, ordem, áudio, legendas e desenhos entre prévia e resultado; manter os casos reproduzíveis como verificações automatizadas pequenas.
6. **Fechar a consistência da interface.** Revisar foco, Enter/Esc, seleção, mensagens curtas, estados vazios e indicação de conteúdo ignorado. Priorizar correções do fluxo existente antes de adicionar ferramentas.
7. **Definir os critérios de publicação estável.** Não haver falhas conhecidas que encerrem o app, percam dados ou produzam exportações divergentes; concluir as validações anteriores e revisar os problemas relatados na prévia. O instalador ainda não é assinado; decidir sobre assinatura de publicação antes da distribuição estável ampla.

As diretrizes permanentes continuam em `AGENTS.md`. Não está prevista uma suíte exaustiva a cada ajuste nem testes manuais pelo agente sem solicitação.
