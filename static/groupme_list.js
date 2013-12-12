var GROUPME_AUTH_TOKEN = "";
var metas = document.getElementsByTagName("meta");

for (i = 0; i < metas.length; i++) {
    if (metas.item(i).getAttribute("name") == "groupme_auth_token") {
        GROUPME_AUTH_TOKEN = metas.item(i).getAttribute("content");
    }
}

function groupme_users_me_callback() {
    var resp = JSON.parse(this.responseText).response;
    var img_src = resp.image_url.replace("http:", "https:");
    var img_el = document.createElement("img");
    img_el.setAttribute("src", img_src);
    img_el.setAttribute("width", "40");

    var text = "Hello, " + resp.name + ".";
    var name_txt = document.createTextNode(text);

    h1_el = document.getElementsByTagName("h1").item(0);
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
        li_el.innerText = group.name;
        group_list.appendChild(li_el);
    }
}

function groupme_bots_callback() {
    var resp = JSON.parse(this.responseText).response;
    var bot_p = document.getElementById("bot_p");
    if (resp.length == 0) {
        bot_p.innerText = "No bots found.";
    } else {
        bot_p.innerText = "Here are your bots:";
    }
    var bot_list = document.getElementById("bot_list");
    for (i = 0; i < resp.length; i++) {
        var bot = resp[i];
        var li_el = document.createElement("li");
        li_el.innerText = bot.name + " on " + bot.group_name;
        bot_list.appendChild(li_el)
    }
}

var xhr_users_me = new XMLHttpRequest();
xhr_users_me.onload = groupme_users_me_callback;
var url = "https://api.groupme.com/v3/users/me?token=" + GROUPME_AUTH_TOKEN;
xhr_users_me.open("get", url);
xhr_users_me.send();

var xhr_groups = new XMLHttpRequest();
xhr_groups.onload = groupme_groups_callback;
url = "https://api.groupme.com/v3/groups?token=" + GROUPME_AUTH_TOKEN;
xhr_groups.open("get", url);
xhr_groups.send();

var xhr_bots = new XMLHttpRequest();
xhr_bots.onload = groupme_bots_callback;
url = "https://api.groupme.com/v3/bots?token=" + GROUPME_AUTH_TOKEN;
xhr_bots.open("get", url);
xhr_bots.send();
