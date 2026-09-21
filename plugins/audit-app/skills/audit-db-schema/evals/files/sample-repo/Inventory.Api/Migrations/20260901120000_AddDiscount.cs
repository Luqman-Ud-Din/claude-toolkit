using Microsoft.EntityFrameworkCore.Migrations;

namespace Inventory.Api.Migrations
{
    // Negative case: fully reversible migration; must NOT be flagged.
    public partial class AddDiscount : Migration
    {
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<decimal>(name: "Discount", table: "Orders", type: "decimal(18,4)", nullable: false, defaultValue: 0m);
        }

        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(name: "Discount", table: "Orders");
        }
    }
}
