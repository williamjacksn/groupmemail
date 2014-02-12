var api_url_base = "https://api.groupme.com/v3/";
var token = groupme_token();

function groupme_token() {
    var cookies = document.cookie.split("; ");
    for (i = 0; i < cookies.length; i++) {
        c = cookies[i].split("=");
        if (c[0] == "groupme_token") {
            return c[1]
        }
    }
}

function add_class(element, class_name) {
    var current_classes = element.className.split(" ");
    current_classes.push(class_name);
    element.className = current_classes.join(" ").trim();
}

function groupme_groups_callback() {
    var resp = JSON.parse(this.responseText).response;

    var group_p = document.getElementById("group_p");
    if (resp.length == 0) {
        group_p.innerHTML = "You don&rsquo;t belong to any groups.";
    } else {
        group_p.innerHTML = "Click on a group to toggle email notifications.";
    }

    var group_list = document.getElementById("group_list");
    for (i = 0; i < resp.length; i++) {
        var group = resp[i];

        var a = document.createElement("a");
        a.setAttribute("id", group.group_id);
        a.setAttribute("href", "/subscribe/" + group.group_id);
        a.innerHTML = group.name + " ";
        add_class(a, "list-group-item");

        var span = document.createElement("span");
        span.setAttribute("id", group.group_id + "_badge")
        add_class(span, "badge");
        span.innerHTML = "Not subscribed ✗";

        a.appendChild(span);
        group_list.appendChild(a);
    }

    var xhr_bots = new XMLHttpRequest();
    xhr_bots.onload = groupme_bots_callback;
    var bots_url = api_url_base + "bots?token=" + token;
    xhr_bots.open("get", bots_url);
    xhr_bots.send();
}

function groupme_bots_callback() {
    var resp = JSON.parse(this.responseText).response;

    for (i = 0; i < resp.length; i++) {
        var bot = resp[i];
        if (bot.callback_url.indexOf("/groupme/incoming/") > -1) {
            mark_subscribed(bot.group_id);
        }
    }
}

function mark_subscribed(group_id) {
    var group_el = document.getElementById(group_id);
    group_el.setAttribute("href", "/unsubscribe/" + group_id);
    group_el.lastChild.innerHTML = "Subscribed ✓";
    add_class(group_el, "list-group-item-success");
}

function startup() {
    var xhr_groups = new XMLHttpRequest();
    xhr_groups.onload = groupme_groups_callback;
    var groups_url = api_url_base + "groups?token=" + token;
    xhr_groups.open("get", groups_url);
    xhr_groups.send();
}

startup();
