{
    "name": "Setup Loka(retail)",
    "version": "1.0",
    "summary": "Konfigurasi otomatis: bahasa, invoice, sales, inventory, purchase, dan CoreTax E-Faktur",
    "description": """
Modul ini mengatur konfigurasi awal Odoo untuk Indonesia secara otomatis:

- Pengaturan modul utama (Invoice, Sales, Inventory, Purchase)
- Aktivasi Bahasa Indonesia
- Pengaturan negara dan mata uang Rupiah (IDR)
- Pemuatan Chart of Accounts (CoA) & Pajak Indonesia
- Integrasi CoreTax E-Faktur
    """,
    "author": "Loka",
    "category": "Localization",
    "depends": [
        "base",
        "uom",
        "product",
        "stock",
        "sale_management",
        "purchase",
        "l10n_id",
        "l10n_id_efaktur_coretax",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_views.xml",
        "views/sale_order_views.xml",
        "views/purchase_order_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}