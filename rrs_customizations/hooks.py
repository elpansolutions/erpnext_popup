app_name = "rrs_customizations"
app_title = "RRS Customizations"
app_publisher = "RRSurgica"
app_description = "RRS Customizations"
app_email = "admin@rrsurgica.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "rrs_customizations",
# 		"logo": "/assets/rrs_customizations/logo.png",
# 		"title": "RRS Customizations",
# 		"route": "/rrs_customizations",
# 		"has_permission": "rrs_customizations.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/rrs_customizations/css/rrs_customizations.css"
app_include_js = "/assets/rrs_customizations/js/rrs_customizations.js"

# include js, css files in header of web template
# web_include_css = "/assets/rrs_customizations/css/rrs_customizations.css"
# web_include_js = "/assets/rrs_customizations/js/rrs_customizations.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "rrs_customizations/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "rrs_customizations/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "rrs_customizations.utils.jinja_methods",
# 	"filters": "rrs_customizations.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "rrs_customizations.install.before_install"
# after_install = "rrs_customizations.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "rrs_customizations.uninstall.before_uninstall"
# after_uninstall = "rrs_customizations.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "rrs_customizations.utils.before_app_install"
# after_app_install = "rrs_customizations.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "rrs_customizations.utils.before_app_uninstall"
# after_app_uninstall = "rrs_customizations.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "rrs_customizations.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "rrs_customizations.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

after_migrate = "rrs_customizations.setup.after_migrate"

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Sales Invoice": {
		"on_submit": "rrs_customizations.overrides.sales_invoice.auto_attach_pdf"
	},
	"Customer": {
		"validate": "rrs_customizations.overrides.customer.sync_sales_person"
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"rrs_customizations.tasks.all"
# 	],
# 	"daily": [
# 		"rrs_customizations.tasks.daily"
# 	],
# 	"hourly": [
# 		"rrs_customizations.tasks.hourly"
# 	],
# 	"weekly": [
# 		"rrs_customizations.tasks.weekly"
# 	],
# 	"monthly": [
# 		"rrs_customizations.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "rrs_customizations.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "rrs_customizations.custom.task.CustomTaskMixin"
# }

override_whitelisted_methods = {
	"frappe.utils.print_format.download_pdf": "rrs_customizations.overrides.sales_invoice.download_pdf"
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "rrs_customizations.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["rrs_customizations.utils.before_request"]
# after_request = ["rrs_customizations.utils.after_request"]

# Job Events
# ----------
# before_job = ["rrs_customizations.utils.before_job"]
# after_job = ["rrs_customizations.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"rrs_customizations.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# Override DocType Class
# ----------------------
override_doctype_class = {
	"Purchase Invoice": "rrs_customizations.overrides.purchase_invoice.RRSPurchaseInvoice"
}
