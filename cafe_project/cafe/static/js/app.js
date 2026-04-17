let cart = JSON.parse(localStorage.getItem("cart")) || [];

function addToCart(name, price) {
  cart.push({name, price});
  localStorage.setItem("cart", JSON.stringify(cart));
  alert("เพิ่มแล้ว");
}

function showCart() {
  let div = document.getElementById("cart");
  let total = 0;

  div.innerHTML = "";

  cart.forEach((i, index) => {
    total += i.price;
    div.innerHTML += `
      <p>${i.name} - ${i.price}
      <button onclick="removeItem(${index})">ลบ</button></p>
    `;
  });

  div.innerHTML += `<h3>Total: ${total}</h3>`;
  localStorage.setItem("total", total);
}

function removeItem(i){
  cart.splice(i,1);
  localStorage.setItem("cart", JSON.stringify(cart));
  showCart();
}

function checkout(){
  window.location="/checkout/";
}

function loadCheckout(){
  let total = localStorage.getItem("total");
  document.getElementById("total").innerText = total;
  document.getElementById("totalInput").value = total;
}

function clearCart(){
  localStorage.clear();
}