# -*- coding: utf-8 -*-
# from odoo import http


# class KioInternalTransderExtension(http.Controller):
#     @http.route('/kio_internal_transfer_extension/kio_internal_transfer_extension', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/kio_internal_transfer_extension/kio_internal_transfer_extension/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('kio_internal_transfer_extension.listing', {
#             'root': '/kio_internal_transfer_extension/kio_internal_transfer_extension',
#             'objects': http.request.env['kio_internal_transfer_extension.kio_internal_transfer_extension'].search([]),
#         })

#     @http.route('/kio_internal_transfer_extension/kio_internal_transfer_extension/objects/<model("kio_internal_transfer_extension.kio_internal_transfer_extension"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('kio_internal_transfer_extension.object', {
#             'object': obj
#         })

