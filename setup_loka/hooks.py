import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Konfigurasi otomatis setelah modul diinstall:
    1. Aktivasi Bahasa Indonesia
    2. Set bahasa user ke Indonesia
    3. Set negara & mata uang (IDR)
    4. Muat Chart of Accounts (CoA) & Pajak
    5. Set lokalisasi fiskal
    """
    _setup_bahasa_indonesia(env)
    _setup_user_language(env)
    _setup_company_indonesia(env)
    _setup_currency_idr(env)
    _load_chart_of_accounts(env)
    _setup_fiscal_localization(env)
    _setup_pricelist_idr(env)
    _setup_inventory_config(env)
    _log_coretax_status(env)


def _setup_pricelist_idr(env):
    """Set mata uang pricelist standar ke Rupiah (IDR)."""
    idr = env.ref('base.IDR', raise_if_not_found=False)
    if not idr:
        # Try finding by code if ref fails
        idr = env['res.currency'].search([('name', '=', 'IDR')], limit=1)
    
    if not idr:
        _logger.warning('product_lti: IDR currency not found.')
        return

    if not idr.active:
        idr.sudo().write({'active': True})

    # 1. Update Public Pricelist (product.list0 is the standard XML ID)
    public_pricelist = env.ref('product.list0', raise_if_not_found=False)
    if not public_pricelist:
        # Fallback: search for any pricelist named "Public Pricelist" or "Default"
        public_pricelist = env['product.pricelist'].search([('name', 'ilike', 'Public')], limit=1)
    
    # Also check for "Default (USD)" specifically reported by user
    usd_pricelist = env['product.pricelist'].search([('name', 'ilike', 'Default (USD)')], limit=1)
    if usd_pricelist and usd_pricelist.currency_id != idr:
        usd_pricelist.sudo().write({
            'currency_id': idr.id,
            'name': 'Default (IDR)'
        })
        _logger.info('product_lti: "Default (USD)" pricelist renamed and updated to IDR.')

    if public_pricelist and public_pricelist.currency_id != idr:
        public_pricelist.sudo().write({'currency_id': idr.id})
        _logger.info('product_lti: Public pricelist updated to IDR.')

    # 2. Update all partners
    # Odoo 17+ uses property_product_pricelist on res.partner
    if public_pricelist:
        # Set as default for new partners (ir.property)
        env['ir.property'].sudo()._set_default(
            'property_product_pricelist',
            'res.partner',
            public_pricelist.id,
            env.company.id
        )
        
        # Update existing partners
        partners = env['res.partner'].search([])
        partners.sudo().write({'property_product_pricelist': public_pricelist.id})
        _logger.info('product_lti: All partners updated to IDR pricelist.')

    _logger.info('product_lti: Pricelist configuration updated to IDR.')


def _setup_bahasa_indonesia(env):
    """Aktifkan Bahasa Indonesia dan muat terjemahan."""
    lang = env['res.lang'].with_context(active_test=False).search(
        [('code', '=', 'id_ID')], limit=1
    )
    if not lang:
        _logger.warning('product_lti: Bahasa Indonesia (id_ID) tidak ditemukan di sistem.')
        return

    if not lang.active:
        lang.sudo().write({'active': True})
        _logger.info('product_lti: Bahasa Indonesia diaktifkan.')

    installed_modules = env['ir.module.module'].search([('state', '=', 'installed')])
    installed_modules._update_translations(['id_ID'])
    _logger.info('product_lti: Terjemahan Bahasa Indonesia berhasil dimuat.')


def _setup_company_indonesia(env):
    """Atur negara perusahaan ke Indonesia."""
    company = env.company
    indonesia = env.ref('base.id', raise_if_not_found=False)

    if not indonesia:
        _logger.warning('product_lti: Data negara Indonesia (base.id) tidak ditemukan.')
        return

    if company.country_id.id != indonesia.id:
        company.sudo().write({'country_id': indonesia.id})

    partner = company.partner_id
    if partner.lang != 'id_ID':
        partner.sudo().write({'lang': 'id_ID'})

    _logger.info('product_lti: Perusahaan dikonfigurasi untuk Indonesia (country + lang).')


def _setup_user_language(env):
    """Atur semua user internal ke Bahasa Indonesia."""
    internal_users = env['res.users'].search([
        ('active', '=', True),
        ('share', '=', False),
    ])
    users_to_update = internal_users.filtered(lambda u: u.lang != 'id_ID')
    if users_to_update:
        users_to_update.sudo().write({'lang': 'id_ID'})
        _logger.info(
            'product_lti: %d user internal diatur ke Bahasa Indonesia (id_ID).',
            len(users_to_update),
        )
    else:
        _logger.info('product_lti: Semua user sudah menggunakan Bahasa Indonesia.')


def _setup_currency_idr(env):
    """Atur mata uang perusahaan ke Rupiah (IDR)."""
    idr = env.ref('base.IDR', raise_if_not_found=False)
    if not idr:
        _logger.warning('product_lti: Mata uang IDR (base.IDR) tidak ditemukan.')
        return

    company = env.company
    if company.currency_id.id == idr.id:
        _logger.info('product_lti: Mata uang perusahaan sudah IDR, lewati.')
        return

    company.sudo().write({'currency_id': idr.id})
    _logger.info('product_lti: Mata uang perusahaan diatur ke IDR (Rupiah Indonesia).')


def _load_chart_of_accounts(env):
    """Muat Chart of Accounts (CoA) Indonesia."""
    env.invalidate_all()
    company = env.company

    if company.chart_template == 'id':
        _logger.info('product_lti: Indonesian CoA sudah terkonfigurasi, lewati.')
        # Tetap hapus _auto_install_template meski CoA sudah ada
        if hasattr(env.registry, '_auto_install_template'):
            del env.registry._auto_install_template
            _logger.info(
                'product_lti: _auto_install_template dihapus '
                '(Indonesian CoA sudah dimuat, generic_coa override dicegah).'
            )
        return

    try:
        env['account.chart.template'].sudo().try_loading('id', company, install_demo=False)
        env.invalidate_all()
        _logger.info('product_lti: Indonesian Chart of Accounts berhasil dimuat.')
    except Exception as exc:
        _logger.error(
            'product_lti: Gagal memuat Indonesian CoA: %s', exc, exc_info=True
        )
        return

    # Hapus callback auto-install yang di-set oleh ir.module.module.write()
    # saat module 'account' diinstall (sebelum hook ini berjalan, company belum
    # punya chart_template → 'generic_coa' dijadwalkan via _register_hook).
    # Karena kita sudah memuat Indonesian CoA, callback generic_coa ini tidak
    # diperlukan dan harus dihapus agar tidak menimpa CoA Indonesia kita.
    if hasattr(env.registry, '_auto_install_template'):
        del env.registry._auto_install_template
        _logger.info(
            'product_lti: _auto_install_template dihapus '
            '(mencegah generic_coa override Indonesian CoA).'
        )


def _setup_fiscal_localization(env):
    """Pastikan lokalisasi fiskal perusahaan adalah Indonesia."""
    company_fields = env['res.company']._fields
    if 'account_fiscal_country_id' not in company_fields:
        _logger.info(
            'product_lti: Field account_fiscal_country_id tidak tersedia '
            '(module account belum terinstall), lewati fiscal localization.'
        )
        return

    indonesia = env.ref('base.id', raise_if_not_found=False)
    if not indonesia:
        _logger.warning('product_lti: Data negara Indonesia (base.id) tidak ditemukan.')
        return

    company = env.company

    # Flush semua pending ORM write + recompute ke DB sebelum SQL langsung
    env.flush_all()

    # Direct SQL: bypass ORM computed field recompute mechanism sepenuhnya.
    # Setelah flush_all(), tidak ada pending recompute yang bisa override.
    env.cr.execute(
        "UPDATE res_company SET account_fiscal_country_id = %s WHERE id = %s",
        [indonesia.id, company.id],
    )

    # Bersihkan cache agar pembacaan ORM berikutnya membaca nilai baru dari DB
    env.invalidate_all()
    _logger.info('product_lti: Fiscal localization diatur ke Indonesia.')


def _log_coretax_status(env):
    """Cek status instalasi CoreTax E-Faktur."""
    coretax = env['ir.module.module'].search(
        [('name', '=', 'l10n_id_efaktur_coretax'), ('state', '=', 'installed')],
        limit=1
    )
    if coretax:
        _logger.info(
            'product_lti: CoreTax E-Faktur (l10n_id_efaktur_coretax) aktif. '
            'Format XML DJP siap digunakan.'
        )
    else:
        _logger.warning(
            'product_lti: CoreTax E-Faktur belum terinstall. '
            'Pastikan l10n_id_efaktur_coretax tersedia di addons path.'
        )


def _setup_inventory_config(env):
    """Aktifkan fitur Varian Produk dan Satuan Ukuran (UoM)."""
    # 1. Aktifkan group_uom dan group_product_variant untuk semua user internal
    group_uom = env.ref('uom.group_uom', raise_if_not_found=False)
    group_variant = env.ref('product.group_product_variant', raise_if_not_found=False)
    
    internal_users = env['res.users'].search([
        ('active', '=', True),
        ('share', '=', False),
    ])

    if group_uom:
        group_uom.sudo().write({'user_ids': [(4, user.id) for user in internal_users]})
        _logger.info('product_lti: Group Satuan Ukuran (UoM) diaktifkan untuk semua user internal.')

    if group_variant:
        group_variant.sudo().write({'user_ids': [(4, user.id) for user in internal_users]})
        _logger.info('product_lti: Group Varian Produk diaktifkan untuk semua user internal.')
