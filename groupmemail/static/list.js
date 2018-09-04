function groupme_token() {
    "use strict";
    let i, c, cookies = document.cookie.split("; ");
    for (i = 0; i < cookies.length; i += 1) {
        c = cookies[i].split("=");
        if (c[0] === "groupme_token") {
            return c[1];
        }
    }
}

const api_url_base = "https://api.groupme.com/v3/";
let token = groupme_token();

function add_class(element, class_name) {
    "use strict";
    let current_classes = element.className.split(" ");
    current_classes.push(class_name);
    element.className = current_classes.join(" ").trim();
}

function mark_subscribed(group_id) {
    "use strict";
    let group_el = document.getElementById(group_id);
    if (group_el) {
        group_el.setAttribute("href", "/unsubscribe/" + group_id);
        group_el.lastChild.innerHTML = "Subscribed ✓";
        add_class(group_el, "list-group-item-success");
    }
}

function groupme_bots_callback() {
    "use strict";
    let i, bot,
        resp = JSON.parse(this.responseText).response;

    for (i = 0; i < resp.length; i += 1) {
        bot = resp[i];
        if (bot["callback_url"].indexOf("/incoming/") > -1) {
            mark_subscribed(bot["group_id"]);
        }
    }
}

function groupme_groups_callback() {
    "use strict";
    let i, group, a, span,
        resp = JSON.parse(this.responseText).response,
        group_p = document.getElementById("group_p"),
        group_list = document.getElementById("group_list"),
        xhr_bots = new XMLHttpRequest(),
        bots_url = api_url_base + "bots?token=" + token;

    if (resp.length === 0) {
        group_p.innerHTML = "You don&rsquo;t belong to any groups.";
    } else {
        group_p.innerHTML = "Click on a group to toggle email notifications.";
    }

    for (i = 0; i < resp.length; i += 1) {
        group = resp[i];

        a = document.createElement("a");
        a.setAttribute("id", group["group_id"]);
        a.setAttribute("href", "/subscribe/" + group["group_id"]);
        a.innerHTML = group.name + " ";
        add_class(a, "list-group-item");

        span = document.createElement("span");
        span.setAttribute("id", group["group_id"] + "_badge");
        add_class(span, "badge");
        span.innerHTML = "Not subscribed ✗";

        a.appendChild(span);
        group_list.appendChild(a);
    }

    xhr_bots.onload = groupme_bots_callback;
    xhr_bots.open("get", bots_url);
    xhr_bots.send();
}

function startup() {
    "use strict";
    let xhr_groups = new XMLHttpRequest(),
        groups_url = api_url_base + "groups?token=" + token;
    xhr_groups.onload = groupme_groups_callback;
    xhr_groups.open("get", groups_url);
    xhr_groups.send();
}

startup();
