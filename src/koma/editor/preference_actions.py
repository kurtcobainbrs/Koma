"""Explicit global preference actions; derived caches only, never project assets."""
async def perform(view, action):
    if action == 'open_backups':
        import asyncio
        from koma.paths import open_directory
        await asyncio.to_thread(open_directory, view.settings.directory / 'backups')
        return
    if action != 'clear_previews':
        raise ValueError('Ação de preferências desconhecida.')
    view.settings.preview_cache.clear()
    view.player.video_preview.clear()
    view.notify('Prévia em cache limpa. As mídias foram preservadas.', 'success')
