from . import models


def post_init_hook(env):
    """Aktifkan fitur Diskon per Baris Order (sale.group_discount_per_so_line) secara otomatis."""
    group = env.ref('sale.group_discount_per_so_line', raise_if_not_found=False)
    if group:
        # Aktifkan melalui res.config.settings agar setting-nya tersimpan
        env['res.config.settings'].sudo().create({
            'group_discount_per_so_line': True,
        }).execute()
