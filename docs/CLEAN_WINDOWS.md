# Validação do Koma em Windows limpo

## Ambiente e objetivo

Use Windows 10/11 x64 padrão, atualizado, com conta comum. Não instale Python, Java, Visual Studio, Flet ou runtimes de depuração. O teste inicial deve ocorrer sem acesso à Internet, para comprovar o uso do cliente desktop incluído. O Blender é opcional no primeiro teste e necessário somente na etapa MP4.

Edições Windows N sem Media Feature Pack precisam de avaliação separada: o cliente Flet inclui plugins que importam Media Foundation. Essa variante não é coberta pela aprovação deste roteiro padrão.

Não confunda este roteiro com uma validação já realizada em máquina limpa. Os resultados obtidos na máquina de desenvolvimento são apenas uma etapa anterior.

## Conteúdo do kit

- `Koma/`: distribuição completa; não separe o executável de `_internal`.
- `SHA256.json`: integridade de todos os arquivos do kit, exceto o próprio manifesto.
- `windows-native-audit.json`: arquitetura e resolução de imports/delay-imports dos binários finais.
- `flet-native-policy.json`: motivo técnico e hashes das duas DLLs órfãs excluídas do cliente fixado.
- `validate_clean_windows.ps1`: verifica hashes, copia o aplicativo para uma pasta nova, registra o ambiente, executa o diagnóstico e abre o documento de teste.
- `new_validation_sandbox.ps1`: gera uma configuração Windows Sandbox opcional; não habilita recursos nem altera configurações do host.

## Executar

1. Confira o SHA-256 do ZIP recebido com o arquivo `.zip.sha256` que o acompanha. Extraia o ZIP inteiro.
2. Em uma VM ou máquina limpa, execute no PowerShell:

   ```powershell
   .\validate_clean_windows.ps1
   ```

   O destino padrão é uma pasta nova `Koma-validacao-<data-hora>` na Área de Trabalho. Para escolher outra:

   ```powershell
   .\validate_clean_windows.ps1 -Destination 'C:\Testes\Koma com espaços e acentos'
   ```

3. O diagnóstico deve terminar sem instalar ou baixar dependências. A pasta `resultados` conterá `ambiente.json`, `diagnostics.json` e amostras geradas (`exemplo.koma`, PDF, imagem de importação, legenda e frames).
4. Confirme no JSON: `ok: true`, `frozen: true`, recursos/documento/PDF/legendas aprovados; MP4 fica `not_requested` nesta etapa. A presença de aliases `WindowsApps\python.exe` no relatório não significa que Python está instalado.
5. O aplicativo deve abrir com o título **Validação Windows**, dois quadros, uma cena e duas conexões. Nenhum console deve ser necessário para usar o editor.

O script não solicita elevação, não instala runtimes, não altera rede, políticas do PowerShell ou configurações de segurança. Se a política local impedir a execução do script, faça o diagnóstico manual abaixo ou utilize o procedimento aprovado pelo administrador da máquina.

## Opção Windows Sandbox

Em um host que **já tenha** Windows Sandbox disponível, execute na pasta extraída:

```powershell
.\new_validation_sandbox.ps1
```

Abra o `Koma-clean.wsb` gerado. Ele desativa a rede e mapeia somente a pasta do kit em leitura. Executa diretamente o diagnóstico de `Koma.exe`, sem script de logon PowerShell e sem depender da política de execução de scripts. O relatório fica em `C:\KomaValidation\diagnostics.json`, e as amostras em uma subpasta `artifacts-*`. Abra `C:\KomaSource\Koma\Koma.exe` e depois o `.koma` gerado para conferir a interface. Não compartilha o AppAkira nem o repositório; a rede do host não é alterada. Esta opção não gera `ambiente.json`, que pertence ao roteiro PowerShell.

Antes de fechar a Sandbox, copie os relatórios para fora pelo procedimento que você escolher: o conteúdo interno é descartado ao encerrá-la. Nenhuma pasta do host é mapeada com permissão de escrita pelo arquivo fornecido.

## Diagnóstico manual sem script PowerShell

Execute o aplicativo empacotado com argumentos, usando uma pasta gravável:

```powershell
$p = Start-Process .\Koma\Koma.exe -ArgumentList '--diagnostics', 'C:\Testes\diagnostics.json' -PassThru -Wait
$p.ExitCode
```

Código `0` significa diagnóstico aprovado; outro valor ou ausência de JSON significa falha. Examine `error` no relatório quando disponível. Esse comando não abre a janela: após o diagnóstico, abra `Koma.exe` e o `.koma` gerado na pasta `artifacts-*` indicada no JSON.

## Conferência manual da interface

Registre aprovado/reprovado e observações para cada item:

| Caso | Resultado esperado |
|---|---|
| Inicialização offline, sem Python/JDK/VS | Janela abre; sem erro de DLL e sem download do Flet |
| Documento de teste | Imagens, cores, duas conexões e legendas preservadas |
| Criar quadro/cena, conectar, mover, recortar | Gestos funcionam e o asterisco indica alterações |
| Desfazer/refazer | Nodes, propriedades e conexões retornam juntos |
| Salvar como em caminho com espaços/acentos | Arquivo `.koma` criado; título atualizado |
| Fechar e reabrir | Conteúdo idêntico, sem depender da imagem original |
| Novo/Abrir com alterações; Cancelar | Documento e histórico permanecem ativos |
| Descartar | Troca de documento sem sobrescrever o arquivo anterior |
| Interrupção controlada do processo de teste | Arquivo → Recuperar sessão oferece a edição não salva |
| Importar `importar.png` gerado | Cópia própria e miniatura corretas |
| Colar imagem/arquivo e atalhos | Colagem no quadro ativo; campos de texto preservam suas teclas |
| Animatic | Ordem, duração, enquadramento e legendas corretos |
| PDF pela interface | Abre no leitor; acentos, fontes, imagens e paginação corretos |
| Redimensionar e usar escala de tela habitual | Menus e propriedades acessíveis |
| Segunda execução offline | Continua funcionando sem cache Flet externo |

Não use documentos pessoais no ensaio de interrupção.

## Segunda etapa: MP4

Instale separadamente o Blender validado (5.0.1) ou disponibilize uma cópia confiável. Isso não é um requisito para abrir ou editar documentos. Execute:

```powershell
.\validate_clean_windows.ps1 -Blender 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe'
```

Use um destino novo se a execução anterior ocorreu no mesmo segundo. O JSON deve informar `mp4: passed`, com `exemplo.mp4` gerado por um **processo iniciado pelo executável empacotado**. A amostra tem 1280 × 720, 24 FPS e 30 frames (1,25 s). Abra o vídeo e confira cortes, enquadramento, acentos e legendas. O MP4 não contém áudio.

Na interface, configure o Blender, exporte a cena, teste cancelamento e confirme que um vídeo anterior é preservado. Também teste Blender ausente/inválido: o erro deve ser claro e o editor deve continuar utilizável.

## Evidências para devolver

- Versão/edição do Windows, arquitetura, escala de tela e se o teste estava offline.
- Hash do ZIP, `ambiente.json`, `diagnostics.json`, relatório da etapa Blender e logs dentro das amostras.
- Resultados da tabela, PDF/MP4 de teste e capturas de eventuais erros.
- Indicação explícita de qualquer runtime que já estava instalado ou foi instalado durante o teste.

Só marque o pacote como homologado após concluir essa conferência. Instalador, assinatura de código e associação de extensão continuam fora deste kit.
