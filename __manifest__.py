{
    'name': 'JinStage Helpdesk Repair Management',
    'version': '17.0.1.1.0',
    'category': 'Helpdesk',
    'summary': 'Extends Helpdesk into a full Repair Management System',
    'author': 'Jinasena Pvt Ltd',
    'license': 'LGPL-3',
    'depends': [
        'helpdesk',
        'helpdesk_fsm',
        'helpdesk_sale',
        'industry_fsm',
        'stock',
        'sale_management',
        'account',
        'product',
    ],
    'data': [
        # --- Security (must load first) ---
        'security/ir.model.access.csv',
        'security/record_rules.xml',

        # --- Master / sequence data ---
        'data/ir_sequence_data.xml',
        'data/helpdesk_team_data.xml',
        'data/repair_ticket_types.xml',
        'data/repair_stages.xml',
        'data/link_stages.xml',

        # --- Views ---
        'views/helpdesk_ticket_type_views.xml',
        'views/helpdesk_stage_views.xml',
        'views/diagnosis_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/project_task_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/actions.xml',
        'views/menus.xml',

        # --- Reports ---
        'report/paper_formats.xml',
        'report/report_actions.xml',
        'report/report_repair_receipt.xml',
        'report/report_repair_status.xml',
        'report/report_repair_final_notice.xml',
        'report/report_repair_final_notice_scrappage.xml',
        'report/report_helpdesk_ticket.xml',

        # --- Automation (last, after models registered) ---
        'data/automation_rules.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
