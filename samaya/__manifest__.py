{
    'name': 'Samaya Industry Package',
    'summary': 'Complete Industry Package combining Construction & Real Estate',
    'description': """
        This module combines multiple industry packages into one:
        - Base Industry Data
        - Construction Builder
        - Construction Developer
        - Real Estate Agency
        
        Features:
        - Construction project management
        - Real estate property management
        - CRM integration for both industries
        - Knowledge base for onboarding
        - Sales and project workflows
    """,
    'version': '1.1',
    'category': 'Industries',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    # Combined Dependencies from all modules
    'depends': [
        # From base_industry_data
        'base',
        'digest',
        'knowledge',
        # From construction
        'crm_enterprise',
        'documents',
        'helpdesk',
        'industry_fsm_stock',
        'purchase_stock',
        'sale_crm',
        'sale_margin',
        'sale_project_forecast',
        # From construction_developer
        'web_studio',
        # From real_estate
        'appointment_crm',
        'base_automation',
        'hr',
        'project_enterprise',
        'sale_commission',
        'sale_project',
        'sign',
        'website_crm',
        'website_sale',
    ],
    'data': [
        # ==========================================
        # BASE INDUSTRY DATA (prefix: bid_)
        # ==========================================
        'data/base_industry_data/knowledge_tour.xml',
        'data/base_industry_data/res_partner_category.xml',

        # ==========================================
        # CONSTRUCTION (prefix: const_)
        # ==========================================
        'data/construction/documents_folder.xml',
        'data/construction/res_config_settings.xml',
        'data/construction/product_category.xml',
        'data/construction/project_task_type.xml',
        'data/construction/ir_ui_view.xml',
        'data/construction/project_project.xml',
        'data/construction/ir_attachment_pre.xml',
        'data/construction/uom_uom.xml',
        'data/construction/planning_role.xml',
        'data/construction/product_template.xml',
        'data/construction/product_product.xml',
        'data/construction/knowledge_cover.xml',
        'data/construction/knowledge_article.xml',
        'data/construction/knowledge_article_favorite.xml',
        'data/construction/mail_message.xml',
        'data/construction/mail_activity_type.xml',
        'data/construction/hr_job.xml',
        'data/construction/sale_order_spreadsheet.xml',
        'data/construction/sale_order_template.xml',
        'data/construction/sale_order_template_line.xml',

        # ==========================================
        # CONSTRUCTION DEVELOPER (prefix: const_dev_)
        # ==========================================
        'data/construction_developer/ir_model_fields.xml',
        'data/construction_developer/ir_actions_server.xml',
        'data/construction_developer/ir_ui_view.xml',
        'data/construction_developer/ir_actions_act_window.xml',
        'data/construction_developer/ir_embedded_actions.xml',
        'data/construction_developer/project_project.xml',
        'data/construction_developer/base_automation.xml',
        'data/construction_developer/qweb_view.xml',
        'data/construction_developer/product_template.xml',
        'data/construction_developer/product_product.xml',
        'data/construction_developer/sale_order_template.xml',
        'data/construction_developer/sale_order_template_line.xml',

        # ==========================================
        # REAL ESTATE (prefix: re_)
        # ==========================================
        'data/real_estate/res_config_settings.xml',
        'data/real_estate/ir_model.xml',
        'data/real_estate/product_attribute.xml',
        'data/real_estate/product_attribute_value.xml',
        'data/real_estate/ir_model_fields.xml',
        'data/real_estate/crm_team.xml',
        'data/real_estate/mail_template.xml',
        'data/real_estate/sign_template.xml',
        'data/real_estate/sign_item_role.xml',
        'data/real_estate/sign_item_type.xml',
        'data/real_estate/sign_item.xml',
        'data/real_estate/product_public_category.xml',
        'data/real_estate/product_category.xml',
        'data/real_estate/sale_commission_plan.xml',
        'data/real_estate/sale_commission_plan_achievement.xml',
        'data/real_estate/ir_actions_server.xml',
        'data/real_estate/base_automation.xml',
        'data/real_estate/ir_actions_act_window.xml',
        'data/real_estate/ir_ui_view.xml',
        'data/real_estate/ir_ui_menu.xml',
        'data/real_estate/ir_model_access.xml',
        'data/real_estate/ir_default.xml',
        'data/real_estate/crm_stage.xml',
        'data/real_estate/project_task_type.xml',
        'data/real_estate/project_project.xml',
        'data/real_estate/product_ribbon.xml',
        'data/real_estate/product_template.xml',
        'data/real_estate/ir_attachment_post.xml',
        'data/real_estate/knowledge_article.xml',
        'data/real_estate/knowledge_article_favorite.xml',
        'data/real_estate/mail_message.xml',
        'data/real_estate/crm_tag.xml',
        'data/real_estate/website_view.xml',
        'data/real_estate/website_page.xml',
        'data/real_estate/website_menu.xml',
        # 'data/real_estate/website_theme_apply.xml',  # Cannot be called during init
    ],
    'demo': [
        # ==========================================
        # BASE INDUSTRY DATA DEMO
        # ==========================================
        'demo/base_industry_data/ir_cron.xml',
        'demo/base_industry_data/res_users.xml',
        'demo/base_industry_data/res_partner.xml',
        'demo/base_industry_data/res_partner_category.xml',

        # ==========================================
        # CONSTRUCTION DEMO
        # ==========================================
        'demo/construction/documents_folder.xml',
        'demo/construction/project_project.xml',
        'demo/construction/documents_document.xml',
        'demo/construction/hr_department.xml',
        'demo/construction/hr_employee.xml',
        'demo/construction/resource_resource.xml',
        'demo/construction/crm_lead.xml',
        'demo/construction/product_supplierinfo.xml',
        'demo/construction/stock_quant.xml',
        'demo/construction/sale_order.xml',
        'demo/construction/sale_order_line.xml',
        'demo/construction/sale_order_confirm.xml',
        'demo/construction/project_task.xml',
        'demo/construction/mail_activity.xml',
        'demo/construction/account_analytic_line.xml',
        'demo/construction/project_update.xml',
        'demo/construction/purchase_order.xml',
        'demo/construction/purchase_order_line.xml',
        'demo/construction/purchase_order_confirm.xml',
        'demo/construction/planning_recurrency.xml',
        'demo/construction/planning_slot.xml',
        'demo/construction/sale_order_spreadsheet.xml',

        # ==========================================
        # CONSTRUCTION DEVELOPER DEMO
        # ==========================================
        'demo/construction_developer/res_partner.xml',
        'demo/construction_developer/project_project.xml',
        'demo/construction_developer/sale_order.xml',
        'demo/construction_developer/sale_order_line.xml',
        'demo/construction_developer/project_task.xml',
        'demo/construction_developer/sale_order_post.xml',

        # ==========================================
        # REAL ESTATE DEMO
        # ==========================================
        'demo/real_estate/res_partner.xml',
        'demo/real_estate/hr_department.xml',
        'demo/real_estate/hr_employee.xml',
        'demo/real_estate/product_template.xml',
        'demo/real_estate/product_image.xml',
        'demo/real_estate/product_template_attribute_line.xml',
        'demo/real_estate/product_template_attribute_value.xml',
        'demo/real_estate/product_product.xml',
        'demo/real_estate/x_product_template_line.xml',
        'demo/real_estate/create_link.xml',
        'demo/real_estate/calendar_event.xml',
        'demo/real_estate/crm_lead.xml',
        'demo/real_estate/mail_activity.xml',
        'demo/real_estate/sale_order.xml',
        'demo/real_estate/sale_order_line.xml',
        'demo/real_estate/project_task.xml',
        'demo/real_estate/sale_commission_plan_user.xml',
        'demo/real_estate/ir_attachment_post.xml',
        'demo/real_estate/website_view.xml',
        'demo/real_estate/website_page.xml',
        'demo/real_estate/website.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # From base_industry_data
            'samaya/static/src/js/my_tour.js',
            # From construction_developer
            'samaya/static/src/widgets/apply_to_section_widget.js',
            'samaya/static/src/widgets/apply_to_section_widget.xml',
            'samaya/static/src/scss/sale_order.scss',
        ],
    },
    'cloc_exclude': [
        'static/src/js/my_tour.js',
        'data/construction/knowledge_article.xml',
        'data/construction_developer/qweb_view.xml',
        'static/src/scss/sale_order.scss',
        'static/src/widgets/apply_to_section_widget.js',
        'static/src/widgets/apply_to_section_widget.xml',
        'data/real_estate/knowledge_article.xml',
        'data/real_estate/website_view.xml',
        'demo/real_estate/website_view.xml',
    ],
    'images': ['images/main.png'],
    'url': "https://www.odoo.com/trial?industry&selected_app=samaya",
    'website': "https://www.odoo.com/industries",
}
