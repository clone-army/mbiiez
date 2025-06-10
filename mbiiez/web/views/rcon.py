from flask import render_template

class view:
    template = "pages/rcon.html"
    view_bag = {}

    def __init__(self, controller):
        if controller.controller_bag:
            self.view_bag = controller.controller_bag

    def render(self):
        return render_template(self.template, view_bag=self.view_bag)
