from flask import Flask, request, render_template

class view:

    template = "pages/logs.html"
    view_bag = {}

    def __init__(self, controller):
        if(controller.controller_bag):
            self.view_bag = controller.controller_bag
            
            for row in self.view_bag['rows']:
                if("errno" in row['log'].lower()):
                    row['class'] = "table-danger"
                    
                elif("exception" in row['log'].lower()):
                    row['class'] = "table-danger"                    
 
                elif("error" in row['log'].lower()):
                    row['class'] = "table-danger" 
                    
                elif("failed" in row['log'].lower()):
                    row['class'] = "table-danger" 
                else:
                    row['class'] = ""

    def render(self):
        return render_template(self.template, view_bag = self.view_bag)
        
        
        