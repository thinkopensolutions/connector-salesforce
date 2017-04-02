# -*- coding: utf-8 -*-
# Copyright 2014-2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import simplejson
from odoo import SUPERUSER_ID
from odoo.tools.translate import _
from odoo.modules.registry import RegistryManager
from odoo import http


class SalesforceOAuthController(http.Controller):
    """Controller that is used to authenticate
    Salesforce using oauth2. This is used
    as the callback URL and it will register tocken
    into `connector.salesforce.backend`
    """

    @http.route('/salesforce/oauth', type='http', auth='none')
    def oauth(self, req, **kwargs):
        """Write Salesforce authorization
        Token in given backend.

        Backend token and backend are GET parameters

        :param req: WSGI request
        :return: success message or raise an error
        :rtype: str
        """
        code = req.params.get('code')
        state = req.params.get('state')
        if not all([code, state]):
            raise ValueError(
                'Authorization process went wrong '
                'with following error %s.' % req.params
            )
        try:
            state_data = simplejson.loads(state)
            backend_id = state_data['backend_id']
            dbname = state_data['dbname']
        except Exception:
            raise ValueError(
                'The authorization process did not return valid values.'
            )
        registry = RegistryManager.get(dbname)
        with registry.cursor() as cr:
            backend_model = registry.get('connector.salesforce.backend')
            backend = backend_model.browse(cr, SUPERUSER_ID, backend_id)
            if not backend:
                raise ValueError('No backend with id %s' % backend_id)
            backend.write({'consumer_code': code})
            # In Salesforce you have a limited time to ask first token
            # after getting conusmer code, else code becomme invalid
            backend._get_token()
        return _("Backend successfully authorized. You should have a new "
                 "authorization code in your backend.")
