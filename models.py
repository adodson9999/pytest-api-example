from flask_restx import fields

class Models:
    def __init__(self, api, PET_TYPE, PET_STATUS):
        self.api = api

        self.pet_model = api.model('Pet', {
            'id': fields.Integer(description='The pet ID'),
            'name': fields.String(required=True, description='The pet name'),
            'type': fields.String(required=True, description='The pet type', enum=PET_TYPE),
            'status': fields.String(description='The pet status', enum=PET_STATUS),
            'order_id': fields.Integer(description='Order id (0 if none)')
        })

        self.order_model = api.model('Order', {
            'id': fields.Integer(readonly=True, description='The order ID'),
            'inven_id': fields.Integer(required=True, description='Inventory item ID'),
            'amount_purchase': fields.Integer(required=True, description='Quantity purchased'),
            "status": fields.String(description="Order/Pet status", enum=PET_STATUS),
        })

        self.order_update_model = api.model('OrderUpdate', {
            'status': fields.String(description='The pet status', enum=PET_STATUS)
        })

        
        self.customer_model = api.model('Customer', {
            'id': fields.Integer(description='The customer ID'),
            'name': fields.String(required=True, description='The customer name'),
            'date': fields.String(required=True, description='The customer purchase date'),
            'purchase': fields.Integer(required=True, description='Item id customer purchases'),
            'email': fields.String(required=True, description='The customer email')
        })
        
        self.inventory_model = self.api.model('Inventory', {
            'id': fields.Integer(description='Inventory Id'),
            'inventory': fields.Integer(description='Inventory of'),
        })
        
        self.vet_model = self.api.model('Vet', {
            'id': fields.Integer(description='The vet ID'),
            'name': fields.String(required=True, description='The customer name'),
            'contact_form': fields.String(required=True, description='How do they like to be contacted'),
            'contact_info': fields.Integer(required=True, description='Contact info of vet')
        })
        
        self.trainer_model = self.api.model('Trainers', {
            'id': fields.Integer(description='The trainer ID'),
            'name': fields.String(required=True, description='The trainer name'),
            'contact_form': fields.String(required=True, description='How do they like to be contacted'),
            'contact_info': fields.Integer(required=True, description='Contact info of trainer')
        })
            
        self.vendor_model = self.api.model('Vendors', {
            'id': fields.Integer(description='The vendor ID'),
            'name': fields.String(required=True, description='The vendor name'),
            'contact_form': fields.String(required=True, description='How do they like to be contacted'),
            'contact_info': fields.String(required=True, description='Contact info of vendor'),
            'point_of_contact': fields.String(required=True, description='Person to talk to about product'),
            'product': fields.Integer(required=True,description='Product inventory id'),
        })
        
        self.events_model = api.model('Event', {
            'id': fields.Integer(description='The event ID'),
            'name': fields.String(required=True, description='The event name'),
            'date': fields.String(required=True, description='Date of event'),
            'location': fields.Integer(required=True, description='Address of event')
        })
            
