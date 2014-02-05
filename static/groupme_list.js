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

function groupme_users_me_callback() {
    var resp = JSON.parse(this.responseText).response;
    var img_src = resp.image_url.replace("http:", "https:");
    var img_el = document.createElement("img");
    img_el.setAttribute("src", img_src);
    img_el.setAttribute("width", "40");

    var text = "Hello, " + resp.name + ".";
    var name_txt = document.createTextNode(text);

    var h1_el = document.getElementsByTagName("h1").item(0);
    h1_el.setAttribute("id", resp.user_id);
    h1_el.textContent = "";
    h1_el.appendChild(img_el);
    h1_el.appendChild(name_txt);
}

function groupme_groups_callback() {
    var resp = JSON.parse(this.responseText).response;
    var group_p = document.getElementById("group_p");
    if (resp.length == 0) {
        group_p.innerText = "No groups found.";
    } else {
        group_p.innerText = "Here are your groups:";
    }
    var group_list = document.getElementById("group_list");
    for (i = 0; i < resp.length; i++) {
        var group = resp[i];
        var li_el = document.createElement("li");
        li_el.setAttribute("id", group.group_id);
        li_el.innerText = group.name;
        group_list.appendChild(li_el);
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
            var group_li = document.getElementById(bot.group_id);
            add_class(group_li, "subscribed");
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
