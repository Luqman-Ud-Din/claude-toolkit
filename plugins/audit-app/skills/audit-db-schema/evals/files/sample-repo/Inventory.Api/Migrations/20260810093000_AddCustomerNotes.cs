using Microsoft.EntityFrameworkCore.Migrations;

namespace Inventory.Api.Migrations
{
    // Planted issue: no reverse step - this migration cannot be rolled back.
    public partial class AddCustomerNotes : Migration
    {
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(name: "Notes", table: "Orders", nullable: true);
            migrationBuilder.Sql("UPDATE Orders SET Notes = '' WHERE Notes IS NULL");
        }

        protected override void Down(MigrationBuilder migrationBuilder)
        {
            // intentionally left blank
        }
    }
}
