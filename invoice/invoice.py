import argparse
import datetime
import logging
import sys

from sqlalchemy.orm.exc import NoResultFound

from . import model
from . import commands
from . import formatters
from . import __version__

l = None

def setup_logging(debug):
    level = logging.INFO
    if debug:
        level = logging.DEBUG
    global l 
    l = logging.getLogger("invoice")
    l.setLevel(level)
    shandler = logging.StreamHandler()
    shandler.setFormatter(logging.Formatter("%(message)s"))
    shandler.setLevel(level)
    l.addHandler(shandler)
    

def parse_args():
    available_formats = formatters.get_formatters()
    default_from = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%d/%b/%Y")
    default_to = datetime.date.today().strftime("%d/%b/%Y")

    parser = argparse.ArgumentParser(description = "Manage invoices")
    parser.add_argument("-f", "--file" , dest = "db", help = "Name of database file", default=argparse.SUPPRESS)
    parser.add_argument("-d", "--debug", dest = "debug", action = "store_true", default = False, help = "Turn on debugging output")
    parser.add_argument("-o", "--output", dest = "output", default = argparse.SUPPRESS, help = "Directory to output generated files")
    parser.add_argument("-v", "--version", dest = "version", action = "store_true", default = False, help = "Display software and db version and quit.")

    subparsers = parser.add_subparsers(title="Commands", dest="command", help = "Commands available")

    init_parser = subparsers.add_parser("init", help="Initialise invoice database")

    db_parser = subparsers.add_parser("db", help="Manage invoice database")
    db_parser.required = True
    db_subparsers = db_parser.add_subparsers(title = "info", dest="op", 
                             metavar="<Database operation>",
                             help = "Manage invoice database")

    db_info_parser = db_subparsers.add_parser("info", help="Summarise database status")
    db_update_parser = db_subparsers.add_parser("update", help="Update the database to the latest version")
    db_update_parser = db_subparsers.add_parser("migrate", help="Create database migrations (not needed for end users)")

    summary_parser = subparsers.add_parser("summary", help="Print a summary of the database contents")
    summary_parser.add_argument("-c", "--chronological", action="store_true", default=argparse.SUPPRESS, help="Order by date rather than id")
    summary_parser.add_argument("-v", "--verbose", action="store_true", default=False, help="Print detailed summary")
    summary_parser.add_argument("-d", "--dump", action = "store_true", default = False, help = "Dump the entire database in a format that can be imported") #TBD


    timesheet_parser = subparsers.add_parser("timesheet", help="Manage timesheets")
    timesheet_subparsers = timesheet_parser.add_subparsers(title = "Timesheet commands", dest="op",
                                                           metavar = "<Timesheet operation>",
                                                           help="Commands to manage timesheets")
    timesheet_subparsers.required = True
    timesheet_show_parser = timesheet_subparsers.add_parser("show", help = "Display a timesheet")
    timesheet_show_parser.add_argument("id", help = "id of timesheet to show")

    timesheet_rm_parser = timesheet_subparsers.add_parser("rm", help="Delete an existing timesheet")
    timesheet_rm_parser.add_argument("id", help = "Id of the timesheet to delete")

    timesheet_edit_parser = timesheet_subparsers.add_parser("edit", help="Edit an existing timesheet")
    timesheet_edit_parser.add_argument("id", help = "Id of timesheet to edit")
    timesheet_edit_parser.add_argument("-d", "--date", help = "Change timesheet date (e.g. 10/Aug/2010)")
    timesheet_edit_parser.add_argument("-e", "--employee", help = "Change employee name")
    timesheet_edit_parser.add_argument("-c", "--client", help="Change timesheet client")
    timesheet_edit_parser.add_argument("-s", "--description", help="Change timesheet description")
    timesheet_edit_parser.add_argument("--edit", action="store_true", default = False, help="Edit timesheet data")
    
    timesheet_add_parser = timesheet_subparsers.add_parser("add", help="Manually add a timesheet")
    timesheet_add_parser.add_argument("-d", "--date", default = datetime.date.today().strftime("%d/%m/%Y"), help = "Timesheet date (10/Aug/2010): Default is %(default)s")
    timesheet_add_parser.add_argument("-e", "--employee", required = True, help="Employee name")
    timesheet_add_parser.add_argument("-c", "--client", required = True, help="Client name")
    timesheet_add_parser.add_argument("-s", "--description", required = True, help="Description of timesheet")
    timesheet_add_parser.add_argument("-t", "--template", required = True, help="Template to use")

    timesheet_ls_parser = timesheet_subparsers.add_parser("ls", help="List timesheets")
    # TBD : Add criteria

    timesheet_import_parser = timesheet_subparsers.add_parser("import", help="Import a new timesheet")
    timesheet_import_parser.add_argument("-d", "--date", default = datetime.date.today().strftime("%d/%b/%Y"), help = "Timesheet date (10/Aug/2010): Default is %(default)s")
    timesheet_import_parser.add_argument("-e", "--employee", required = True, help="Employee name")
    timesheet_import_parser.add_argument("-c", "--client", required = True, help="Client name")
    timesheet_import_parser.add_argument("-s", "--description", required = True, help="Description of timesheet")
    timesheet_import_parser.add_argument("-t", "--template", required = True, help="Template to use")
    timesheet_import_parser.add_argument("timesheet")

    timesheet_parse_parser = timesheet_subparsers.add_parser("parse", help="Parse and print a timesheet")
    timesheet_parse_parser.add_argument("timesheet", help = "Timesheet file")

    timesheet_generate_parser = timesheet_subparsers.add_parser("generate", help = "Generate a timesheet")
    timesheet_generate_parser.add_argument("-d", "--id",
                                           default = -1,
                                           help = "Generate timesheet with this id (Overrides other options)")
    timesheet_generate_parser.add_argument("-f", "--from", 
                                           default = default_from,
                                           help = "Generate all timesheets since this date (10/Aug/2010). Default is %(default)s")
    timesheet_generate_parser.add_argument("-t", "--to",
                                           default = default_to,
                                           help = "Generate all timesheets till this date (10/Aug/2010). Default is %(default)s")
    timesheet_generate_parser.add_argument("--format", 
                                           default = argparse.SUPPRESS,
                                           choices = available_formats,
                                           help = "Format to output invoice.")
    timesheet_generate_parser.add_argument("-e", "--employee",
                                           help = "Generate timesheets only for this employee.")
    timesheet_generate_parser.add_argument("-c", "--client",
                                           default = '',
                                           help = "Which client to generate invoices for.")
    timesheet_generate_parser.add_argument("-w", "--overwrite",
                                           action="store_true",
                                           default = argparse.SUPPRESS,
                                           help = "Overwrite existing generated files.")
    



    account_parser = subparsers.add_parser("account", help="Manage Accounts")
    account_subparsers = account_parser.add_subparsers(title = "Account commands", dest="op", 
                                                       metavar = "<Account operation>", 
                                                       help="Commands to manipulate accounts")
    account_subparsers.required = True
    account_edit_parser = account_subparsers.add_parser("edit", help = "Edit an existing account")
    account_edit_parser.add_argument("name", help = "Name of account")
    account_edit_parser.add_argument("-s", "--signatory", help = "Name of signatory")
    account_edit_parser.add_argument("-a", "--address", help = "Billing address account")
    account_edit_parser.add_argument("-p", "--phone", help = "Phone number")
    account_edit_parser.add_argument("-e", "--email", help = "Email address")
    account_edit_parser.add_argument("--pan", help = "Pan number")
    account_edit_parser.add_argument("--serv", help = "Service tax number")
    account_edit_parser.add_argument("--bank-details", help = "Bank details. Must include bank name, address, account number, account holders name, IFSC code and any other details.")
    account_edit_parser.add_argument("--prefix", help = "Invoice number prefix")

    account_add_parser = account_subparsers.add_parser("add", help = "Create a new account")
    account_add_parser.add_argument("-n", "--name", help = "Name of account", required = True)
    account_add_parser.add_argument("-s", "--signatory", help = "Name of signatory", required = True)
    account_add_parser.add_argument("-a", "--address", help = "Billing address account", required = True)
    account_add_parser.add_argument("-p", "--phone", help = "Phone number", required = True)
    account_add_parser.add_argument("-e", "--email", help = "Email address", required = True)
    account_add_parser.add_argument("--pan", help = "Pan number")
    account_add_parser.add_argument("--serv", help = "Service tax number")
    account_add_parser.add_argument("--bank-details", required = True, help = "Bank details. Must include bank name, address, account number, account holders name, IFSC code and any other details.")
    account_add_parser.add_argument("--prefix", help = "Invoice number prefix")

    account_add_parser = account_subparsers.add_parser("ls", help = "List accounts")

    account_show_parser = account_subparsers.add_parser("show", help = "Show account")
    account_show_parser.add_argument("account", help = "Name of account")

    client_parser = subparsers.add_parser("client", help = "Manage clients")
    client_subparsers = client_parser.add_subparsers(title = "Client commands", dest = "op",
                                                     metavar = "<Client operation>",
                                                     help = "Commands to manipulate clients")
    client_subparsers.required = True
    client_add_parser = client_subparsers.add_parser("add", help = "Add a new client")
    client_add_parser.add_argument("-n", "--name", help = "Name of client", required = True)
    client_add_parser.add_argument("-a", "--account", help = "Name of account under which this client is to be registered", required = True)
    client_add_parser.add_argument("-b", "--bunit", help = "Units to bill in (e.g. INR)", required = True)
    client_add_parser.add_argument("--address", help = "Client billing address", required = True)
    client_add_parser.add_argument("-p", "--period", help = "Day of month on which this customer should be billed", required = True)

    client_list_parser = client_subparsers.add_parser("ls", help = "List clients")

    client_show_parser = client_subparsers.add_parser("show", help = "Show details of a client")
    client_show_parser.add_argument("name", help = "Name of client to show")

    client_edit_parser = client_subparsers.add_parser("edit", help = "Edit client")
    client_edit_parser.add_argument("name", help = "Name of client to edit")
    client_edit_parser.add_argument("-a", "--account", help = "Name of account under which this client is to be registered")
    client_edit_parser.add_argument("-b", "--bunit", help = "Billing unit for this client")
    client_edit_parser.add_argument("--address", help = "Client billing address")
    client_edit_parser.add_argument("-p", "--period", help = "Day of month on which this customer should be billed")

    template_parser = subparsers.add_parser("template", help = "Manage templates")
    template_subarsers = template_parser.add_subparsers(title = "Template commands", dest = "op",
                                                      metavar = "<Template operation>",
                                                      help = "Commands to manipulate Templates")
    template_subarsers.required = True
    template_add_parser = template_subarsers.add_parser("add", help = "Add a new template")
    template_add_parser.add_argument("-n", "--name",  required = True, help = "Name of invoice")
    template_add_parser.add_argument("-d", "--desc",  default = '', help = "Description of template")
    template_add_parser.add_argument("-l", "--letterhead",  default = '', help = "Add a letterhead to use as a base PDF")
    template_edit_parser = template_subarsers.add_parser("edit", help = "Edit a new template")
    template_edit_parser.add_argument("name", help = "Name of invoice to edit")
    template_edit_parser.add_argument("-d", "--desc",  default=argparse.SUPPRESS, help = "Change description to this")
    template_edit_parser.add_argument("-l", "--letterhead", default=argparse.SUPPRESS, help = "Change template letterhead to this file")
    template_del_parser = template_subarsers.add_parser("rm", help = "Delete template")
    template_del_parser.add_argument("name", help = "Name of invoice to delete")
    template_ls_parser = template_subarsers.add_parser("ls", help = "List templates")


    invoice_parser = subparsers.add_parser("invoice", help = "Manage invoices")
    invoice_subparsers = invoice_parser.add_subparsers(title = "Invoice commands", dest = "op",
                                                      metavar = "<Invoice operation>",
                                                      help = "Commands to manipulate invoices")
    invoice_subparsers.required = True
    invoice_show_parser = invoice_subparsers.add_parser("show", help = "Display an invoice")
    invoice_show_parser.add_argument("id", help = "id of invoice to show")

    invoice_list_parser = invoice_subparsers.add_parser("ls", help = "List invoices")
    invoice_list_parser.add_argument("-f", "--from", 
                                     default = default_from,
                                     help = "Show only invoices since this date (10/Aug/2010). Use 'a' to list from beginning. Default is %(default)s")
    invoice_list_parser.add_argument("-t", "--to",
                                     default = default_to,
                                     help = "Show only invoices till this date (10/Aug/2010). Default is %(default)s")
    invoice_list_parser.add_argument("-c", "--client",
                                     help = "Show only invoices for this client")
    invoice_list_parser.add_argument("-g", "--tag",
                                     action = "append",
                                     help = "Show only invoices with these tags. Can be given multiple times.")
    invoice_list_parser.add_argument("-a", "--all",
                                     action="store_true",
                                     default=False,
                                     help = "Show all invoices (including cancelled)")
    
    

    invoice_add_parser = invoice_subparsers.add_parser("add", help = "Add a new invoice")
    invoice_add_parser.add_argument("-c", "--client", required = True, help = "Which client this invoice is for")
    invoice_add_parser.add_argument("-t", "--template", required = True, help = "Which template to use for this invoice")
    invoice_add_parser.add_argument("-d", "--date", default = datetime.date.today().strftime("%d/%b/%Y"), help = "Invoice date (10/Aug/2010): Default is %(default)s")
    invoice_add_parser.add_argument("-p", "--particulars", required = True, 
                                    help = "Subject line for this invoice")
    invoice_delete_parser = invoice_subparsers.add_parser("rm", help = "Delete an invoice")
    invoice_delete_parser.add_argument("id", type = int, help = "Id of invoice to delete")

    invoice_edit_parser = invoice_subparsers.add_parser("edit", help = "Edits an existing invoice")
    invoice_edit_parser.add_argument("id", type = int, help = "Id of invoice to edit")
    invoice_edit_parser.add_argument("-c", "--client", help = "Change client for this invoice")
    invoice_edit_parser.add_argument("-t", "--template", help = "Change template for this invoice")
    invoice_edit_parser.add_argument("-d", "--date", help = "Change invoice date (10/Aug/2010)")
    invoice_edit_parser.add_argument("-p", "--particulars", help = "Subject line for this invoice")
    invoice_edit_parser.add_argument("-e", "--edit", action = "store_true", default = False, help = "Edit actual invoice content")
    tag_group = invoice_edit_parser.add_mutually_exclusive_group()
    tag_group.add_argument("-a", "--add-tags", action = "append", help = "Tags to add to the invoice. Can be specified multiple times.")
    tag_group.add_argument("-r", "--replace-tags", action = "append", help = "Tags attached to the invoice will be replaced by these. Can be specified multiple times.")
    
    invoice_generate_parser = invoice_subparsers.add_parser("generate", help = "Generate an invoice")
    invoice_generate_parser.add_argument("-i", "--id",
                                         default=-1,
                                         help = "Generate invoice with this id. (Overrides other filtering)")
    invoice_generate_parser.add_argument("-f", "--from", 
                                         default = default_from,
                                         help = "Generate all invoices since this date (10/Aug/2010). Default is %(default)s")
    invoice_generate_parser.add_argument("-t", "--to",
                                         default = default_to,
                                         help = "Generate all invoices till this date (10/Aug/2010). Default is %(default)s")
    invoice_generate_parser.add_argument("--format", 
                                         default = argparse.SUPPRESS,
                                         choices = available_formats,
                                         help = "Format to output invoice.")
    invoice_generate_parser.add_argument("-c", "--client",
                                         default = '',
                                         help = "Which client to generate invoices for.")
    invoice_generate_parser.add_argument("-w", "--overwrite",
                                         action="store_true",
                                         default = argparse.SUPPRESS,
                                         help = "Overwrite existing generated files.")



    tag_parser = subparsers.add_parser("tag", help = "Manage invoice tags")
    tag_subparsers = tag_parser.add_subparsers(title = "Tag commands", dest = "op",
                                                metavar = "<Tag operation>",
                                                help = "Commands to manipulate invoice tags")
    tag_subparsers.required = True
    tag_add_parser = tag_subparsers.add_parser("add", help = "Create a new tag")
    tag_add_parser.add_argument("name", help = "Name of new tag to add")

    tag_rm_parser = tag_subparsers.add_parser("rm", help = "Delete an existing tag")
    tag_rm_parser.add_argument("name", help = "Name of new tag to delete")

    tag_list_parser = tag_subparsers.add_parser("ls", help = "List all tags")

    args = parser.parse_args()
    if not args.command and not args.version:
        parser.error("Subcommand needed")
    return args


def dispatch(args):
    cmd = args.command if hasattr(args, "command") else ""
    l.debug("Command is '%s'", cmd)
    if args.version:
        cmd = "version"
    try:
        dispatcher = commands.get_commands()
        command_class = dispatcher[cmd]
        try:
            command_handler = command_class(args)
        except TypeError:
            sys.exit(-1)
        command_handler()
    except NoResultFound:
        sys.exit(-1)
    except IOError:
        sys.exit(-1)

def main():
    args = parse_args()
    setup_logging(args.debug)
    l.debug("Invoice version '%s'", __version__)
    dispatch(args)

if __name__ == '__main__':
    main()
    
