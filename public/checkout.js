(function () {
  const RAZORPAY_SRC = "https://checkout.razorpay.com/v1/checkout.js";
  let razorpayPromise = null;

  function ensureRazorpayLoaded() {
    if (window.Razorpay) {
      return Promise.resolve(window.Razorpay);
    }
    if (!razorpayPromise) {
      razorpayPromise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = RAZORPAY_SRC;
        script.async = true;
        script.onload = () => window.Razorpay ? resolve(window.Razorpay) : reject(new Error("Razorpay SDK missing after load."));
        script.onerror = () => reject(new Error("Failed to load Razorpay checkout."));
        document.head.appendChild(script);
      });
    }
    return razorpayPromise;
  }

  async function createOrder(plan) {
    const endpoint = `/api/payments/create-order?plan=${encodeURIComponent(plan)}`;
    const response = await fetch(endpoint, { method: "POST" });
    if (!response.ok) {
      const message = await response.text().catch(() => "Failed to create order");
      throw new Error(message || "Failed to create order");
    }
    return response.json();
  }

  async function openCheckout(plan) {
    const normalizedPlan = (typeof plan === "string" ? plan : "pro").toLowerCase();
    const allowedPlans = new Set(["pro", "elite"]);
    const planToUse = allowedPlans.has(normalizedPlan) ? normalizedPlan : "pro";

    let RazorpayCtor;
    try {
      RazorpayCtor = await ensureRazorpayLoaded();
    } catch (error) {
      console.error(error);
      alert("Payment service unavailable. Please try again in a moment.");
      return;
    }

    let payload;
    try {
      payload = await createOrder(planToUse);
    } catch (error) {
      console.error(error);
      alert("Failed to create order. Please try again.");
      return;
    }

    const { key, order, customer } = payload || {};
    if (!key || !order || !order.id) {
      console.error("Invalid order payload", payload);
      alert("Payment could not be started. Please contact support.");
      return;
    }

    const rzp = new RazorpayCtor({
      key,
      order_id: order.id,
      amount: order.amount,
      currency: order.currency,
      name: "Evara",
      description: `${planToUse.toUpperCase()} plan subscription`,
      image: "/public/evara-logo.svg",
      prefill: customer || {},
      theme: { color: "#007AFF" },
      handler: async function (response) {
        try {
          const verifyResponse = await fetch("/api/payments/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(response)
          });
          if (!verifyResponse.ok) {
            console.warn("Verification failed", await verifyResponse.text());
          }
        } catch (error) {
          console.error("Verification request failed", error);
        }
        window.location.href = `/thank-you?plan=${encodeURIComponent(planToUse)}`;
      },
      modal: {
        ondismiss: function () {
          console.log("Checkout closed");
        }
      }
    });

    rzp.on("payment.failed", function (event) {
      console.error(event.error);
      alert("Payment failed. Please try again.");
    });

    rzp.open();
  }

  window.openCheckout = openCheckout;
})();
