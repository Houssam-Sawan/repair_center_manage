// Copyright (c) 2026, Houssam Sawan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Document Edit Control Settings", {
    apply_to_doctype(frm) {
        if (!frm.doc.apply_to_doctype) return;

        frappe.call({
            method: "frappe.desk.form.load.getdoctype",
            args: { doctype: frm.doc.apply_to_doctype },
            callback(r) {
                frm._target_meta = r.message;
            }
        });
    }
});

frappe.ui.form.on("Tab Edit Rules", {
    status(frm, cdt, cdn) {
        let tabs = (frm._target_meta?.fields || [])
            .filter(f => f.fieldtype === "Section Break")
            .map(f => `${f.label} (${f.fieldname})`);

        frappe.meta.get_docfield(
            cdt, "section_break", frm.docname
        ).options = tabs.join("\n");
    }
});

frappe.ui.form.on("Field Edit Rules", {
    status(frm, cdt, cdn) {
        let fields = (frm._target_meta?.fields || [])
            .filter(f =>
                !["Section Break", "Column Break"].includes(f.fieldtype)
            )
            .map(f => `${f.label} (${f.fieldname})`);

        frappe.meta.get_docfield(
            cdt, "fieldname", frm.docname
        ).options = fields.join("\n");
    }
});

frappe.ui.form.on("Child Field Edit Rules", {
    parent_fieldname(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        let table = frm._target_meta.fields.find(
            f => f.fieldname === row.parent_fieldname
        );

        if (!table) return;

        frappe.call({
            method: "frappe.desk.form.load.getdoctype",
            args: { doctype: table.options },
            callback(r) {
                let fields = r.message.fields
                    .filter(f => f.fieldtype !== "Column Break")
                    .map(f => `${f.label} (${f.fieldname})`);

                frappe.meta.get_docfield(
                    cdt, "child_fieldname", frm.docname
                ).options = fields.join("\n");
            }
        });
    }
});
