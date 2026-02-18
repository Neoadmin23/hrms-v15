frappe.query_reports["Location Attendance Report"] = {
    filters: [
        {
            fieldname: "employee",
            label: "Employee",
            fieldtype: "Link",
            options: "Employee"
        },
        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date"
        },
        {
            fieldname: "locations",
            label: "Locations",
            fieldtype: "Link",
            options: "Shift Location"
        },
        {
            fieldname: "show_all_locations",
            label: "Show All Locations",
            fieldtype: "Check",
            default: 0
        }
    ]
};