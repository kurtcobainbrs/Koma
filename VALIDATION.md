# Validação da extração

## Atualização do pacote com ícones e arraste — 26/10/2026

- Pacote atualizado em `dist/Koma/Koma.exe`, com cliente Flet próprio e Material Icons completos (1.645.184 bytes), sem remoção de ícones dinâmicos.
- 197 testes Python e 7 testes Flutter aprovados.
- Auditoria do pacote: 108 binários x64 sem dependências ausentes ou runtimes de depuração.
- Diagnóstico do executável aprovado para recursos, documento/histórico/imagens, PDF e legendas. MP4 não foi solicitado nesta atualização.
- Usuário confirmou na versão empacotada: ícones corretos, arrastar e soltar funcionando e Ctrl+Z desfazendo normalmente.
- ZIP `dist/Koma-windows-x64-validation.zip` validado: 481 arquivos com hashes internos e checksum externo conferidos. Cliente empacotado idêntico ao cliente corrigido validado.
- Publicação usa preparação separada, verifica a auditoria antes da promoção e preserva a versão anterior, com rollback em falha. ZIPs anteriores também são preservados. Nenhum projeto ou imagem original do usuário foi sobrescrito pelo processo de atualização.
- Homologação em uma máquina Windows limpa continua pendente antes de publicação geral.

## Registro anterior — 24/10/2026

Data: 24/10/2026. Ambiente: Windows 11, Python 3.12.14, Flet 1.0.5, Pillow 13.0.0, ReportLab 4.5.1, Blender 5.0.1.

- 128 testes automatizados aprovados: núcleo, gestos, serialização Flet, documentos, recuperação, conflitos, fechamento, runner de vídeo, política nativa e diagnóstico da distribuição.
- PDF de integração gerado com duas páginas; textos e identificação KOMA conferidos por extração. A paginação visual completa ainda precisa de revisão manual.
- MP4 real produzido pelo Blender e reaberto nele: 1280 × 720, 24 FPS, 30 frames, 1,25 segundo. Inclui preparação de enquadramento e legendas.
- `.koma` reaberto em outra sessão com igualdade de todos os dados.
- Wheel instalado em diretório separado e importado desse diretório, sem importar `akira`. Fontes e script do Blender presentes.
- Executável Windows aberto com o `.koma` de integração: imagens, nodes, conexões e título do documento conferidos na janela.
- Build Windows inclui uma verificação explícita do script externo do Blender, fonte, configuração de legendas e cliente Flet.
- `pip check`: nenhuma dependência quebrada.
- Arquivos do AppAkira preservados: mesmo hash SHA-256 agregado antes/depois, `0b62d8571b9f67a6db0ed1a63fdaf2a9d53aadb08b8a1c825770527e3e5ce1e4`; Git sem alterações.

## Pendências antes de publicar

1. Executar a distribuição em uma máquina Windows limpa, sem Python e sem o ambiente de desenvolvimento.
2. Conferir PDF visualmente e exportações pela interface do executável empacotado.
3. Decidir instalador, assinatura, ícone definitivo e associação de extensão.

## Correção dos avisos de DLLs

Os avisos vinham de dois arquivos órfãos do cliente Flet 1.0.5: `dartjni.dll` importava `jvm.dll`; `zlib.dll` importava `VCRUNTIME140D.dll` e `ucrtbased.dll`. A inspeção dos 30 binários originais não encontrou imports nem delay-imports desses dois arquivos pelos demais binários. A busca dos nomes em bytes ASCII/UTF-16 nos arquivos retidos também não encontrou referências, e o manifesto nativo estava vazio.

O empacotamento do Koma exclui somente esses dois arquivos, depois de validar a versão, seus hashes e a ausência dessas referências. O cliente instalado em `.flet` permanece intacto. Mudança de versão/hash ou nova referência bloqueia o build para revisão; não há supressão dos avisos do PyInstaller.

O pacote ajustado passou na auditoria PE de **84 binários x64**, sem dependências ausentes ou runtimes debug. Runtimes Visual C++ de release precisam estar no pacote, mesmo que existam no host. O cliente Flutter, que é outro processo, não pode usar a cópia do runtime pertencente ao Python em `_internal`. Dependências do sistema são limitadas a uma lista explícita de DLLs do Windows padrão e aos API sets. O build final não apresentou avisos de bibliotecas ausentes.

Os módulos opcionais `flet.testing`, `flet.security` e `flet.fastapi` não participam da coleta de submódulos do desktop, evitando avisos sobre numpy, cryptography e flet-web que não atendem a funcionalidades do Koma.

O lançamento do Blender pelo executável congelado restaura temporariamente a busca padrão de DLLs e remove caminhos internos do pacote do PATH do subprocesso, conforme a [orientação do PyInstaller para programas externos](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application). O diretório de DLLs do processo Koma é restaurado após o lançamento, inclusive em falha.

## Preparação para Windows limpo

- Kit `dist/Koma-windows-x64-validation.zip`, acompanhado de SHA-256 e manifesto de todos os arquivos internos.
- Auditorias de dependências e política do Flet incluídas no kit.
- Diagnóstico `Koma.exe --diagnostics REPORT.json`, sem Python instalado; MP4 opcional por `--blender`.
- Roteiro PowerShell testado sobre o ZIP extraído em caminho com espaços/acentos, PATH mínimo e dados isolados: `frozen: true`, recursos/documento/PDF/legendas aprovados.
- MP4 gerado pelo **executável empacotado copiado do ZIP**, iniciando Blender 5.0.1: diagnóstico aprovado e vídeo reaberto no Blender com 1280 × 720, 24 FPS e 30 frames.
- Configuração Windows Sandbox gerada e conferida como XML: rede desativada, somente o kit mapeado em leitura e diagnóstico executado diretamente pelo aplicativo. A Sandbox **não foi executada** nesta sessão.
- [Roteiro completo e critérios de aprovação](docs/CLEAN_WINDOWS.md).

O ensaio com PATH mínimo foi feito na máquina de desenvolvimento. Não equivale a uma instalação limpa nem comprova todos os caminhos de carga dinâmica de bibliotecas. A homologação em Windows limpo, a conferência manual da interface/exportações e a variante Windows N permanecem pendentes.

Logs e amostras locais ficam em `build/`; os artefatos de distribuição ficam em `dist/`. Ambos são ignorados pelo Git. Não foram criados commits nem pull requests.
