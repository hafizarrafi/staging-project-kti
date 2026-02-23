# -*- coding: utf-8 -*-
# from odoo import http


# class AnotherEstate(http.Controller):
#     @http.route('/another_estate/another_estate', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/another_estate/another_estate/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('another_estate.listing', {
#             'root': '/another_estate/another_estate',
#             'objects': http.request.env['another_estate.another_estate'].search([]),
#         })

#     @http.route('/another_estate/another_estate/objects/<model("another_estate.another_estate"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('another_estate.object', {
#             'object': obj
#         })

