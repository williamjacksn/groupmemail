var cookies = document.cookie.split("; ");
for (i = 0; i < cookies.length; i++) {
    c = cookies[i].split("=");
    if (c[0] = "groupme_token") {
        var groupme_token = c[1]
    }
}

function add_class(element, class_name) {
    var current_classes = element.className.split(" ");
    current_classes.push(class_name);
    element.className = current_classes.join(" ").trim();
}

function drop_class(element, class_name) {
    var current_classes = element.className.split(" ");
    var resulting_classes = [];
    for (i = 0; i < current_classes.length; i++) {
        if (current_classes[i] != class_name) {
            resulting_classes.push(current_classes[i]);
        }
    }
    element.className = resulting_classes.join(" ").trim();
}

function groupme_users_me_callback() {
    var resp = JSON.parse(this.responseText).response;
    var img_src = resp.image_url.replace("http:", "https:");
    var img_el = document.createElement("img");
    img_el.setAttribute("src", img_src);
    img_el.setAttribute("width", "40");

    document.getElementById("groupme_username").textContent = resp.name;
}

function groupme_groups_callback() {
    var resp = JSON.parse(this.responseText).response;
    var group_p = document.getElementById("group_p");
    if (resp.length == 0) {
        group_p.innerText = "No groups found.";
    } else {
        group_p.innerText = "Click on a group to toggle email notifications.";
    }
    var group_list = document.getElementById("group_list");
    for (i = 0; i < resp.length; i++) {
        var group = resp[i];

        var a_el = document.createElement("a");
        a_el.setAttribute("id", group.group_id);
        a_el.setAttribute("href", "#");
        a_el.innerText = group.name;
        add_class(a_el, "list-group-item");

        var new_span = document.createElement("span");
        new_span.setAttribute("id", group.group_id + "_badge")
        add_class(new_span, "badge");
        new_span.innerText = "Not subscribed ✗";
        a_el.appendChild(new_span);
        group_list.appendChild(a_el);
    }

    var xhr_bots = new XMLHttpRequest();
    xhr_bots.onload = groupme_bots_callback;
    var url = "https://api.groupme.com/v3/bots?token=" + groupme_token;
    xhr_bots.open("get", url);
    xhr_bots.send();
}

function groupme_bots_callback() {
    var resp = JSON.parse(this.responseText).response;
    for (i = 0; i < resp.length; i++) {
        var bot = resp[i];
        if (bot.callback_url.indexOf("/groupme/incoming/") > -1) {
            var group_el = document.getElementById(bot.group_id);
            var span = group_el.lastChild;
            span.innerText = "Subscribed ✓";
            add_class(group_el, "list-group-item-success");
        }
    }
}

var xhr_users_me = new XMLHttpRequest();
xhr_users_me.onload = groupme_users_me_callback;
var url = "https://api.groupme.com/v3/users/me?token=" + groupme_token;
xhr_users_me.open("get", url);
xhr_users_me.send();

var xhr_groups = new XMLHttpRequest();
xhr_groups.onload = groupme_groups_callback;
url = "https://api.groupme.com/v3/groups?token=" + groupme_token;
xhr_groups.open("get", url);
xhr_groups.send();
