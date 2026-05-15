from flask import Flask, request, render_template

class view:

    template = "pages/dashboard.html"
    view_bag = {}
    def __init__(self, controller):
        if controller and controller.controller_bag:
            self.view_bag = controller.controller_bag
        else:
            self.view_bag = {}
    def render(self):
        return render_template(self.template, view_bag=self.view_bag)