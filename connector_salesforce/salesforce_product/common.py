# -*- coding: utf-8 -*-
# Copyright 2014-2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields
from ..unit.binder import SalesforceBinder


class SalesforceProduct(models.Model):
    _inherit = 'salesforce.binding'
    _inherits = {'product.product': 'odoo_id'}
    _name = 'connector.salesforce.product'
    _description = 'Import SF Product into res.partner model'

    odoo_id = fields.Many2one('product.product',
                                 string='Product',
                                 required=True,
                                 index=True,
                                 ondelete='restrict')

    _sql_constraints = [
        ('sf_id_uniq', 'unique(backend_id, salesforce_id)',
         'A Product with same Salesforce id already exists')
    ]

SalesforceBinder._model_name.append('connector.salesforce.product')
