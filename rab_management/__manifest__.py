{
    'name': 'RAB Management',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Budget Plan (RAB) Management',
    'author': 'YourCompany',
    'depends': [
        'base',
        'web',
        'mail',
        'product',
        'contacts',
        'sale',
        'sale_project',
        'purchase',
        'stock',
        'project',   
    ],
    'data': [
            'security/res_groups.xml',
            'security/ir.model.access.csv',
            'data/ir_sequence_data.xml',
            'data/product_category.xml',
            'data/product_service.xml',
            'views/rab_owl_actions.xml',
            'views/partner_view.xml',
            'views/rab_view.xml',
            'views/inventory_view.xml',
            'views/project_task_view.xml',
            'views/project_subtask_view.xml',
            'views/project_project_view.xml',
            'views/product_view.xml',
            'views/menu.xml',
            'views/rab_vendor_comparison.xml',
            # 'views/project_task_material_views.xml',
            # 'views/project_task_material_view.xml',
            'views/project_material_master_view.xml',
            'views/project_equipment_master_view.xml',
          

            # 'views/rab_vendor_comparison_pivot.xml',
            
            # khusus report document
            'views/report/report_delivery.xml',
            'views/report/purchase_report.xml',
            'views/report/sales_report.xml',




    ],
    'application': True,
    'license': 'LGPL-3',

   'assets': {
       
        'web.assets_backend': [
            'rab_management/static/src/owl/actions/rab_vendor_comparison.js',
            'rab_management/static/src/owl/services/rab_service.js',
            'rab_management/static/src/owl/components/vendor_matrix/vendor_matrix.js',
            'rab_management/static/src/owl/xml/rab_vendor_comparison.xml',
            'rab_management/static/src/owl/components/vendor_matrix/vendor_matrix.xml',
            'rab_management/static/src/scss/rab_vendor_comparison.scss',
        ],
    },





    


    

}
