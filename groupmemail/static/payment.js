let stripe = Stripe(document.getElementById("stripe-publishable-key").getAttribute("content"));

let checkout_button = document.getElementById("checkout-button");
checkout_button.addEventListener("click", function () {
    stripe.redirectToCheckout({
        items: [{
            sku: document.getElementById("stripe-sku").getAttribute("content"),
            quantity: 1
        }],
        successUrl: document.getElementById("payment-success-url").getAttribute("href"),
        cancelUrl: document.getElementById("payment-cancel-url").getAttribute("href"),
        customerEmail: document.getElementById("user-email").getAttribute("content")
    })
        .then(function (result) {
            if (result.error) {
                console.log(result.error.message);
            }
        });
});
