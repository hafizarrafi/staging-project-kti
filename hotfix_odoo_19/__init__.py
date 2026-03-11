from . import models


# def pre_init_hook(cr):
#     """Set default color_scheme for existing records before upgrade."""
#     cr.execute("""
#         UPDATE res_users_settings
#         SET color_scheme = 'dark'
#         WHERE color_scheme IS NULL
#     """)


# def post_init_hook(env):
#     """Set default color_scheme for existing records after install."""
#     env.cr.execute("""
#         UPDATE res_users_settings
#         SET color_scheme = 'dark'
#         WHERE color_scheme IS NULL
#     """)
